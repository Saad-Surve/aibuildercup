"""Analysis worker: consume a queued `analyze` job and produce findings + heatmap bins.

Pipeline (`docs/technical-design/diagrams.md` section 6):

analysis run created -> reviewers fan out in parallel over transcript chunks ->
findings validated and normalised -> aggregated into heatmap bins -> findings and
bins stored -> `analysis.ready`.

Idempotent: a job that already reached a terminal state (`succeeded`/`failed`/
`cancelled`) is left untouched so retried Pub/Sub deliveries converge. Reviewer
results are persisted as they land, so a half-finished run still shows what its
completed reviewers found.
"""

import logging
from typing import Any

from fastapi import BackgroundTasks

from app.agents.analysis_coordinator import (
    DEFAULT_CHUNK_CHARS,
    DimensionOutcome,
    build_review_contexts,
    build_reviewers,
    chunk_segments,
    run_reviewers,
)
from app.agents.reviewer_base import SegmentRef
from app.config import Settings, get_settings
from app.errors import NotFoundError
from app.events import build_event, topic_for_event
from app.providers import get_providers
from app.providers.base import LlmProvider
from app.schemas.analysis import AnalysisDimension, AnalysisRunStatus, Finding
from app.schemas.jobs import JobStatus
from app.services.analysis_service import AnalysisService
from app.services.cost import estimate_cost_usd
from app.services.firestore_service import (
    asset_path,
    get_firestore_client,
    project_object_prefix,
    project_path,
)
from app.services.heatmap import aggregate_bins, summarize_findings
from app.services.job_service import JobService
from app.services.markdown_repair import normalize_markdown
from app.services.pubsub_service import PubSubClient, get_pubsub_client
from app.services.storage_service import StorageClient, get_storage_client
from app.services.transcript_service import TranscriptService
from app.services.user_service import UserService
from app.services.video_tools import (
    GcsContextArtifactStore,
    MediaToolkit,
    ffmpeg_available,
)

logger = logging.getLogger(__name__)

TERMINAL_STATUSES = frozenset(
    {JobStatus.succeeded.value, JobStatus.failed.value, JobStatus.cancelled.value}
)

#: Persona markdown is context, not content: keep the prompt bounded.
PERSONA_EXCERPT_CHARS = 4000

#: Progress: fan-out is the expensive part, so it owns most of the bar.
_REVIEW_START_PERCENT = 10
_REVIEW_END_PERCENT = 85


async def run_analysis(
    *,
    owner_uid: str,
    project_id: str,
    job_id: str,
    jobs: JobService,
    analyses: AnalysisService,
    transcripts: TranscriptService,
    users: UserService,
    storage: StorageClient,
    llm: LlmProvider,
    settings: Settings,
    pubsub: PubSubClient | None = None,
    max_chunk_chars: int = DEFAULT_CHUNK_CHARS,
) -> str | None:
    """Run one multi-reviewer analysis job. Returns the analysis run id, or None."""
    try:
        job = jobs.load_for_worker(owner_uid=owner_uid, project_id=project_id, job_id=job_id)
    except NotFoundError:
        logger.warning("analyze job %s not found; skipping", job_id)
        return None

    if job.get("status") in TERMINAL_STATUSES:
        logger.info("analyze job %s already %s; skipping", job_id, job.get("status"))
        return (job.get("input") or {}).get("analysisRunId")

    analysis_run_id = (job.get("input") or {}).get("analysisRunId")
    if not analysis_run_id:
        jobs.mark_failed(
            owner_uid=owner_uid,
            project_id=project_id,
            job_id=job_id,
            message="Analysis job is missing its analysis run id.",
            code="ANALYZE_FAILED",
        )
        return None

    try:
        run = analyses.load_run_document(
            owner_uid=owner_uid, project_id=project_id, analysis_run_id=analysis_run_id
        )
    except NotFoundError:
        logger.warning("analyze job %s: run %s not found", job_id, analysis_run_id)
        jobs.mark_failed(
            owner_uid=owner_uid,
            project_id=project_id,
            job_id=job_id,
            message="Analysis run not found.",
            code="ANALYZE_FAILED",
        )
        return None

    dimensions = [
        AnalysisDimension(value) for value in run.get("requestedDimensions", [])
    ]
    if not dimensions:
        jobs.mark_failed(
            owner_uid=owner_uid,
            project_id=project_id,
            job_id=job_id,
            message="Analysis run has no dimensions to run.",
            code="ANALYZE_FAILED",
        )
        return None

    jobs.mark_running(
        owner_uid=owner_uid,
        project_id=project_id,
        job_id=job_id,
        step="loading_transcript",
        message="Loading transcript",
    )
    try:
        transcript = transcripts.get_by_id(
            owner_uid=owner_uid,
            project_id=project_id,
            transcript_id=str(run.get("transcriptId") or ""),
        )
    except NotFoundError:
        jobs.mark_failed(
            owner_uid=owner_uid,
            project_id=project_id,
            job_id=job_id,
            message="Transcript for this analysis is gone. Start a new analysis.",
            code="ANALYZE_FAILED",
        )
        analyses.finish_run(
            owner_uid=owner_uid,
            project_id=project_id,
            analysis_run_id=analysis_run_id,
            status=AnalysisRunStatus.failed,
            summary=summarize_findings([]),
            cost_usd=0.0,
            completed_dimensions=[],
            error={"code": "TRANSCRIPT_NOT_FOUND", "message": "Transcript missing."},
        )
        return None

    segments = [
        SegmentRef(
            segment_id=segment.segmentId,
            start_ms=segment.startMs,
            end_ms=segment.endMs,
            text=segment.text,
        )
        for segment in transcript.segments
    ]
    if not segments:
        jobs.mark_failed(
            owner_uid=owner_uid,
            project_id=project_id,
            job_id=job_id,
            message="Transcript has no segments to review.",
            code="ANALYZE_FAILED",
        )
        analyses.finish_run(
            owner_uid=owner_uid,
            project_id=project_id,
            analysis_run_id=analysis_run_id,
            status=AnalysisRunStatus.failed,
            summary=summarize_findings([]),
            cost_usd=0.0,
            completed_dimensions=[],
            error={"code": "EMPTY_TRANSCRIPT", "message": "No speech to review."},
        )
        return None

    persona_markdown, persona_version = _load_persona(users, storage, owner_uid)
    audience = _load_audience(users, owner_uid)
    video_title, thumbnail_concept = _load_packaging(analyses, owner_uid, project_id)
    platform = str(run.get("platform") or "youtube")
    reviewer_run_ids = {
        AnalysisDimension(key): value
        for key, value in (run.get("reviewerRunIds") or {}).items()
    }

    chunks = chunk_segments(segments, max_chars=max_chunk_chars)
    contexts = build_review_contexts(
        chunks,
        persona=persona_markdown,
        platform=platform,
        audience=audience,
        language=transcript.language,
        duration_ms=transcript.durationMs,
        video_title=video_title,
        thumbnail_concept=thumbnail_concept,
    )
    analyses.mark_running(
        owner_uid=owner_uid,
        project_id=project_id,
        analysis_run_id=analysis_run_id,
        chunk_count=len(chunks),
    )
    logger.info(
        "analyze job %s: %d dimension(s) x %d chunk(s)",
        job_id,
        len(dimensions),
        len(chunks),
    )

    visual_tools = _build_visual_tools(
        analyses,
        storage,
        settings,
        owner_uid=owner_uid,
        project_id=project_id,
        run=run,
        duration_ms=transcript.durationMs,
    )
    context_store = (
        _build_context_store(storage, owner_uid, project_id, analysis_run_id)
        if visual_tools is not None
        else None
    )
    reviewers = build_reviewers(
        llm,
        model=settings.model_reviewer,
        dimensions=dimensions,
        visual_tools=visual_tools,
        context_store=context_store,
        grounding_enabled=settings.truth_grounding_enabled,
    )
    completed: list[DimensionOutcome] = []
    all_findings: list[Finding] = []
    total_dimensions = max(1, len(dimensions))

    async def on_outcome(outcome: DimensionOutcome) -> None:
        completed.append(outcome)
        all_findings.extend(outcome.findings)
        _persist_outcome(
            analyses,
            pubsub,
            owner_uid=owner_uid,
            project_id=project_id,
            analysis_run_id=analysis_run_id,
            outcome=outcome,
        )
        jobs.update_progress(
            owner_uid=owner_uid,
            project_id=project_id,
            job_id=job_id,
            percent=_REVIEW_START_PERCENT
            + int(
                (_REVIEW_END_PERCENT - _REVIEW_START_PERCENT)
                * len(completed)
                / total_dimensions
            ),
            step=f"reviewer:{outcome.dimension.value}",
            message=f"{len(completed)}/{total_dimensions} reviewers finished",
        )

    try:
        outcomes = await run_reviewers(
            reviewers,
            contexts,
            max_concurrency=settings.max_reviewer_concurrency,
            reviewer_run_ids=reviewer_run_ids,
            on_outcome=on_outcome,
        )
    except Exception as exc:  # noqa: BLE001 - record the failure on the job and the run
        logger.exception("analyze job %s: fan-out failed", job_id)
        jobs.mark_failed(
            owner_uid=owner_uid,
            project_id=project_id,
            job_id=job_id,
            message=f"Analysis failed: {exc}",
            code="ANALYZE_FAILED",
        )
        analyses.finish_run(
            owner_uid=owner_uid,
            project_id=project_id,
            analysis_run_id=analysis_run_id,
            status=AnalysisRunStatus.failed,
            summary=summarize_findings([]),
            cost_usd=0.0,
            completed_dimensions=[],
            error={"code": "ANALYZE_FAILED", "message": str(exc)[:500]},
        )
        return None

    findings = [finding for outcome in outcomes for finding in outcome.findings]
    jobs.update_progress(
        owner_uid=owner_uid,
        project_id=project_id,
        job_id=job_id,
        percent=_REVIEW_END_PERCENT,
        step="aggregating",
        message="Building the heatmap",
    )

    bins = aggregate_bins(findings, duration_ms=transcript.durationMs)
    summary = summarize_findings(findings)
    analyses.save_bins(
        owner_uid=owner_uid,
        project_id=project_id,
        analysis_run_id=analysis_run_id,
        bins=bins,
    )

    succeeded = [o for o in outcomes if o.status.value == "succeeded"]
    cost_usd = round(
        sum(
            estimate_cost_usd(
                outcome.usage,
                input_price_per_mtok=settings.llm_input_price_per_mtok,
                output_price_per_mtok=settings.llm_output_price_per_mtok,
            )
            for outcome in outcomes
        ),
        6,
    )
    failed_count = len(outcomes) - len(succeeded)
    if not succeeded:
        status = AnalysisRunStatus.failed
    elif failed_count:
        status = AnalysisRunStatus.partial_failure
    else:
        status = AnalysisRunStatus.ready
    error = (
        {
            "code": "SOME_REVIEWERS_FAILED",
            "message": f"{failed_count} reviewer(s) failed.",
        }
        if failed_count
        else None
    )

    run_model = analyses.finish_run(
        owner_uid=owner_uid,
        project_id=project_id,
        analysis_run_id=analysis_run_id,
        status=status,
        summary=summary,
        cost_usd=cost_usd,
        completed_dimensions=[o.dimension for o in succeeded],
        error=error,
    )
    if status is AnalysisRunStatus.failed:
        jobs.mark_failed(
            owner_uid=owner_uid,
            project_id=project_id,
            job_id=job_id,
            message="Every reviewer failed. Nothing to show for this run.",
            code="ANALYZE_FAILED",
        )
    else:
        jobs.mark_succeeded(
            owner_uid=owner_uid,
            project_id=project_id,
            job_id=job_id,
            output={
                "artifactIds": [],
                "storagePaths": [],
                "analysisRunId": analysis_run_id,
                "findingCount": len(findings),
                "heatmapBinCount": len(bins),
            },
            message=(
                "Completed" if status is AnalysisRunStatus.ready else "Completed with gaps"
            ),
        )
    _publish(
        pubsub,
        event_type="analysis.ready",
        owner_uid=owner_uid,
        project_id=project_id,
        job_id=job_id,
        payload={
            "analysisRunId": analysis_run_id,
            "status": status.value,
            "overallScore": run_model.overallScore,
            "findingCount": len(findings),
            "heatmapBinCount": len(bins),
            "costEstimateUsd": cost_usd,
            "personaVersion": persona_version,
        },
    )
    logger.info(
        "analyze job %s done: %d findings, %d bins, status=%s, $%.4f",
        job_id,
        len(findings),
        len(bins),
        status.value,
        cost_usd,
    )
    return analysis_run_id


def _persist_outcome(
    analyses: AnalysisService,
    pubsub: PubSubClient | None,
    *,
    owner_uid: str,
    project_id: str,
    analysis_run_id: str,
    outcome: DimensionOutcome,
) -> None:
    """Record one reviewer's result the moment it lands."""
    try:
        analyses.save_reviewer_outcome(
            owner_uid=owner_uid,
            project_id=project_id,
            analysis_run_id=analysis_run_id,
            outcome=outcome,
        )
        analyses.save_findings(
            owner_uid=owner_uid,
            project_id=project_id,
            analysis_run_id=analysis_run_id,
            findings=outcome.findings,
        )
    except Exception:  # noqa: BLE001 - a write failure must not lose the other reviewers
        logger.exception(
            "failed to persist %s reviewer result", outcome.dimension.value
        )
        return
    _publish(
        pubsub,
        event_type="reviewer.completed",
        owner_uid=owner_uid,
        project_id=project_id,
        payload={
            "analysisRunId": analysis_run_id,
            "reviewerRunId": outcome.reviewer_run_id,
            "dimension": outcome.dimension.value,
            "status": outcome.status.value,
            "findingCount": len(outcome.findings),
        },
    )


def _publish(
    pubsub: PubSubClient | None,
    *,
    event_type: str,
    owner_uid: str,
    project_id: str,
    job_id: str | None = None,
    payload: dict[str, Any] | None = None,
) -> None:
    """Best-effort announcement; the data is already persisted."""
    if pubsub is None:
        return
    event = build_event(
        event_type=event_type,
        owner_uid=owner_uid,
        project_id=project_id,
        job_id=job_id,
        payload=payload,
    )
    try:
        pubsub.publish(topic=topic_for_event(event_type), event=event)
    except Exception:  # noqa: BLE001
        logger.exception("failed to publish %s", event_type)


def _load_persona(
    users: UserService, storage: StorageClient, owner_uid: str
) -> tuple[str, int | None]:
    """Persona markdown (bounded) plus the version it came from."""
    try:
        user = users.get_user(owner_uid) or {}
    except Exception:  # noqa: BLE001 - persona is context, never a hard dependency
        return "", None
    persona = user.get("persona") or {}
    version = persona.get("version")
    version = int(version) if isinstance(version, (int, float)) else None
    storage_path = persona.get("storagePath")
    if not storage_path:
        return "", version
    try:
        markdown = normalize_markdown(storage.download_text(storage_path))
    except Exception:  # noqa: BLE001
        logger.warning("could not read persona for %s", owner_uid)
        return "", version
    return markdown[:PERSONA_EXCERPT_CHARS], version


def _load_audience(users: UserService, owner_uid: str) -> str:
    try:
        answers = users.get_onboarding(owner_uid).answers or {}
    except Exception:  # noqa: BLE001
        return ""
    return str(answers.get("audience") or "").strip()[:500]


def _load_packaging(
    analyses: AnalysisService, owner_uid: str, project_id: str
) -> tuple[str, str]:
    """(video title, thumbnail concept) for the packaging-aware reviewers.

    The project name doubles as the video title. Never a hard dependency.
    """
    try:
        project = analyses.client.get_document(project_path(owner_uid, project_id)) or {}
    except Exception:  # noqa: BLE001
        return "", ""
    title = str(project.get("name") or "").strip()[:200]
    thumbnail = str(project.get("thumbnailConcept") or "").strip()[:500]
    return title, thumbnail


def _build_visual_tools(
    analyses: AnalysisService,
    storage: StorageClient,
    settings: Settings,
    *,
    owner_uid: str,
    project_id: str,
    run: dict[str, Any],
    duration_ms: int,
) -> MediaToolkit | None:
    """Build the FFmpeg-backed visual toolkit for this run, or None if unavailable.

    The source is handed to FFmpeg as a short-lived signed URL, so the API never has to
    download the whole video into memory. Every failure here is non-fatal: reviewers
    simply run transcript-only, exactly as before the tools existed.
    """
    if not settings.review_visual_tools_enabled:
        return None
    if not ffmpeg_available(settings.ffmpeg_path):
        logger.warning(
            "visual reviewer tools disabled: ffmpeg not found at %s", settings.ffmpeg_path
        )
        return None
    asset_id = run.get("sourceAssetId")
    if not asset_id:
        return None
    try:
        asset = analyses.client.get_document(
            asset_path(owner_uid, project_id, str(asset_id))
        )
    except Exception:  # noqa: BLE001 - visual context is an enhancement, not a dependency
        logger.warning("visual reviewer tools: could not load source asset", exc_info=True)
        return None
    if not asset or asset.get("ownerUid") != owner_uid:
        return None
    storage_path = asset.get("storagePath")
    if not storage_path:
        return None
    try:
        source = storage.signed_download_url(str(storage_path), expires_seconds=3600)
    except Exception:  # noqa: BLE001
        logger.warning("visual reviewer tools: cannot sign source video URL", exc_info=True)
        return None
    logger.info("visual reviewer tools enabled for %s/%s", owner_uid, project_id)
    return MediaToolkit(
        source=source,
        duration_ms=duration_ms,
        ffmpeg_path=settings.ffmpeg_path,
        window_seconds=settings.visual_clip_window_seconds,
        max_requests=settings.max_visual_context_requests,
        max_rounds=settings.visual_tool_max_rounds,
    )


def _build_context_store(
    storage: StorageClient,
    owner_uid: str,
    project_id: str,
    analysis_run_id: str,
) -> GcsContextArtifactStore:
    """Store reviewer-fetched footage under the project prefix (covered by project delete)."""
    prefix = (
        f"{project_object_prefix(owner_uid, project_id)}"
        f"review-context/{analysis_run_id}/"
    )
    return GcsContextArtifactStore(storage, prefix)


def build_worker_services(
    *,
    jobs: JobService,
    analyses: AnalysisService,
    transcripts: TranscriptService,
    users: UserService,
    storage: StorageClient,
    llm: LlmProvider,
    settings: Settings,
    pubsub: PubSubClient | None = None,
) -> dict[str, Any]:
    """Bundle worker deps for call sites (API-triggered inline run, Pub/Sub handler)."""
    return {
        "jobs": jobs,
        "analyses": analyses,
        "transcripts": transcripts,
        "users": users,
        "storage": storage,
        "llm": llm,
        "settings": settings,
        "pubsub": pubsub,
    }


def live_worker_dependencies() -> dict[str, Any]:
    """Build the real (non-test) dependency bundle once, for any live call site."""
    firestore = get_firestore_client()
    settings = get_settings()
    storage = get_storage_client()
    jobs = JobService(firestore)
    return build_worker_services(
        jobs=jobs,
        analyses=AnalysisService(firestore, jobs=jobs, settings=settings),
        transcripts=TranscriptService(firestore, storage=storage),
        users=UserService(firestore, storage=storage),
        storage=storage,
        llm=get_providers().llm,
        settings=settings,
        pubsub=get_pubsub_client(),
    )


def analysis_after_response(
    background_tasks: BackgroundTasks,
    *,
    owner_uid: str,
    project_id: str,
    job_id: str,
) -> None:
    """Run the analysis worker after the HTTP response is sent.

    `POST /projects/{id}/analysis` returns immediately with the run and job ids; the
    fan-out runs here. Builds live dependencies, so call sites that need fakes (tests)
    must inject their own scheduler instead.
    """
    background_tasks.add_task(
        run_analysis,
        owner_uid=owner_uid,
        project_id=project_id,
        job_id=job_id,
        **live_worker_dependencies(),
    )
