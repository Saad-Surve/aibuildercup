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

import asyncio
import logging
from dataclasses import replace
from datetime import UTC, datetime
from typing import Any

from fastapi import BackgroundTasks

from app.agents.adjudicator import ADJUDICATOR_PROMPT_VERSION, adjudicate
from app.agents.analysis_coordinator import (
    DEFAULT_CHUNK_CHARS,
    DimensionOutcome,
    build_review_contexts,
    build_reviewers,
    chunk_segments,
    rubric_call_estimate,
    run_reviewers,
    run_rubric_review,
)
from app.agents.editor import EDITOR_PROMPT_VERSION, edit_findings
from app.agents.reviewer_base import ReviewContext, ReviewFrame, SegmentRef
from app.config import Settings, get_settings
from app.errors import NotFoundError
from app.events import build_event, topic_for_event
from app.providers import get_providers
from app.providers.base import LlmProvider, LlmUsage
from app.schemas.analysis import (
    AdjudicatorSummary,
    AnalysisDimension,
    AnalysisRunStatus,
    EditorSummary,
    Finding,
    InterestCalibration,
    InterestCurve,
    InterestMoment,
    InterestPoint,
    Severity,
)
from app.schemas.jobs import JobStatus
from app.services.analysis_service import AnalysisService
from app.services.cost import estimate_cost_usd
from app.services.finding_library_links import enrich_finding_library_links
from app.services.firestore_service import (
    asset_path,
    get_firestore_client,
    project_object_prefix,
    project_path,
)
from app.services.heatmap import (
    aggregate_bins,
    effective_findings,
    merge_coverage,
    summarize_findings,
)
from app.services.interest import (
    CurveMoment,
    bin_texts,
    build_curve,
    load_model,
    score_windows,
    words_from_segments,
)
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
from app.workers.guard import serialize_job

logger = logging.getLogger(__name__)

TERMINAL_STATUSES = frozenset(
    {JobStatus.succeeded.value, JobStatus.failed.value, JobStatus.cancelled.value}
)

#: Persona markdown is context, not content: keep the prompt bounded.
PERSONA_EXCERPT_CHARS = 4000

#: Progress: fan-out is the expensive part, so it owns most of the bar.
_REVIEW_START_PERCENT = 10
_REVIEW_END_PERCENT = 85


@serialize_job
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
        job = await asyncio.to_thread(
            jobs.load_for_worker, owner_uid=owner_uid, project_id=project_id, job_id=job_id
        )
    except NotFoundError:
        logger.warning("analyze job %s not found; skipping", job_id)
        return None

    if job.get("status") in TERMINAL_STATUSES:
        logger.info("analyze job %s already %s; skipping", job_id, job.get("status"))
        return (job.get("input") or {}).get("analysisRunId")

    analysis_run_id = (job.get("input") or {}).get("analysisRunId")
    if not analysis_run_id:
        await asyncio.to_thread(
            jobs.mark_failed,
            owner_uid=owner_uid,
            project_id=project_id,
            job_id=job_id,
            message="Analysis job is missing its analysis run id.",
            code="ANALYZE_FAILED",
        )
        return None

    try:
        run = await asyncio.to_thread(
            analyses.load_run_document,
            owner_uid=owner_uid,
            project_id=project_id,
            analysis_run_id=analysis_run_id,
        )
    except NotFoundError:
        logger.warning("analyze job %s: run %s not found", job_id, analysis_run_id)
        await asyncio.to_thread(
            jobs.mark_failed,
            owner_uid=owner_uid,
            project_id=project_id,
            job_id=job_id,
            message="Analysis run not found.",
            code="ANALYZE_FAILED",
        )
        return None

    dimensions = [AnalysisDimension(value) for value in run.get("requestedDimensions", [])]
    if not dimensions:
        await asyncio.to_thread(
            jobs.mark_failed,
            owner_uid=owner_uid,
            project_id=project_id,
            job_id=job_id,
            message="Analysis run has no dimensions to run.",
            code="ANALYZE_FAILED",
        )
        return None

    await asyncio.to_thread(
        jobs.mark_running,
        owner_uid=owner_uid,
        project_id=project_id,
        job_id=job_id,
        step="loading_transcript",
        message="Loading transcript",
    )
    try:
        transcript = await asyncio.to_thread(
            transcripts.get_by_id,
            owner_uid=owner_uid,
            project_id=project_id,
            transcript_id=str(run.get("transcriptId") or ""),
        )
    except NotFoundError:
        await asyncio.to_thread(
            jobs.mark_failed,
            owner_uid=owner_uid,
            project_id=project_id,
            job_id=job_id,
            message="Transcript for this analysis is gone. Start a new analysis.",
            code="ANALYZE_FAILED",
        )
        await asyncio.to_thread(
            analyses.finish_run,
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
        await asyncio.to_thread(
            jobs.mark_failed,
            owner_uid=owner_uid,
            project_id=project_id,
            job_id=job_id,
            message="Transcript has no segments to review.",
            code="ANALYZE_FAILED",
        )
        await asyncio.to_thread(
            analyses.finish_run,
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

    persona_markdown, persona_version = await asyncio.to_thread(
        _load_persona, users, storage, owner_uid
    )
    audience = await asyncio.to_thread(_load_audience, users, owner_uid)
    video_title, thumbnail_concept, project_brief = await asyncio.to_thread(
        _load_packaging, analyses, owner_uid, project_id
    )
    platform = str(run.get("platform") or "youtube")
    reviewer_run_ids = {
        AnalysisDimension(key): value for key, value in (run.get("reviewerRunIds") or {}).items()
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
        project_brief=project_brief,
    )
    await asyncio.to_thread(
        analyses.mark_running,
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

    visual_tools = await asyncio.to_thread(
        _build_visual_tools,
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
    if visual_tools is not None:
        await asyncio.to_thread(
            jobs.update_progress,
            owner_uid=owner_uid,
            project_id=project_id,
            job_id=job_id,
            percent=_REVIEW_START_PERCENT,
            step="inspecting_video",
            message="Inspecting the opening, middle, and ending",
        )
        contexts = await _add_sampled_frames(contexts, visual_tools, context_store)
    reviewers = build_reviewers(
        llm,
        model=settings.model_reviewer,
        dimensions=dimensions,
        visual_tools=visual_tools,
        context_store=context_store,
        grounding_enabled=settings.truth_grounding_enabled,
    )
    # The interest curve needs only the transcript, so it runs alongside the reviewers.
    interest_task = (
        asyncio.create_task(
            _predict_interest(
                llm,
                settings,
                segments=segments,
                duration_ms=transcript.durationMs,
                title=video_title,
                language=transcript.language,
            )
        )
        if settings.interest_curve_enabled
        else None
    )

    # Admit the independent rubric before reviewer fan-out. Keep a conservative
    # allowance for all reviewer chunks/tool rounds, interest and durable prior calls.
    async def reserve_rubric() -> str | None:
        return await asyncio.to_thread(
            analyses.reserve_rubric_call,
            owner_uid=owner_uid,
            project_id=project_id,
            analysis_run_id=analysis_run_id,
        )

    async def settle_rubric(slot: str, usage: LlmUsage | None, error: str | None) -> None:
        await asyncio.to_thread(
            analyses.settle_rubric_call,
            owner_uid=owner_uid,
            slot=slot,
            usage=usage,
            error=error,
        )

    rubric_task = None
    try:
        spent_before, adjudicator_before, editor_before = await asyncio.gather(
            asyncio.to_thread(
                analyses.spent_usd,
                owner_uid=owner_uid,
                project_id=project_id,
                exclude_run_id=analysis_run_id,
            ),
            asyncio.to_thread(
                analyses.adjudicator_spent_usd,
                owner_uid=owner_uid,
                project_id=project_id,
                analysis_run_id=analysis_run_id,
            ),
            asyncio.to_thread(
                analyses.editor_spent_usd,
                owner_uid=owner_uid,
                project_id=project_id,
                analysis_run_id=analysis_run_id,
            ),
        )
        rounds = 1 + (settings.visual_tool_max_rounds if visual_tools is not None else 0)
        reviewer_allowance = (
            len(reviewers)
            * len(contexts)
            * rounds
            * estimate_cost_usd(
                # Observed reviewer calls use ~15-31k input and 4-6k output tokens.
                LlmUsage(input_tokens=32_000, output_tokens=8_192),
                input_price_per_mtok=settings.llm_input_price_per_mtok,
                output_price_per_mtok=settings.llm_output_price_per_mtok,
            )
        )
        interest_allowance = (
            estimate_cost_usd(
                LlmUsage(input_tokens=48_000, output_tokens=16_000),
                input_price_per_mtok=settings.llm_input_price_per_mtok,
                output_price_per_mtok=settings.llm_output_price_per_mtok,
            )
            if interest_task is not None
            else 0.0
        )
        parallel_budget = (
            settings.max_project_cost_usd
            - spent_before
            - adjudicator_before
            - editor_before
            - reviewer_allowance
            - interest_allowance
        )
        if parallel_budget >= rubric_call_estimate(settings):
            rubric_task = asyncio.create_task(
                run_rubric_review(
                    llm,
                    settings=settings,
                    segments=segments,
                    context=contexts[0],
                    media=tuple(frame.media for c in contexts for frame in c.sampled_frames),
                    budget_usd=parallel_budget,
                    reserve_call=reserve_rubric,
                    settle_call=settle_rubric,
                )
            )
        # Near the cap, retain the serial path: actual reviewer charges may free
        # enough room for the same rubric request after the reviewers settle.
    except Exception:
        logger.warning("Could not reserve concurrent rubric allowance", exc_info=True)

    completed: list[DimensionOutcome] = []
    outcome_lock = asyncio.Lock()
    total_dimensions = max(1, len(dimensions))

    async def on_outcome(outcome: DimensionOutcome) -> None:
        async with outcome_lock:
            completed.append(outcome)
            await asyncio.to_thread(
                _persist_outcome,
                analyses,
                pubsub,
                owner_uid=owner_uid,
                project_id=project_id,
                analysis_run_id=analysis_run_id,
                outcome=outcome,
            )
            await asyncio.to_thread(
                jobs.update_progress,
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
        for task in (interest_task, rubric_task):
            if task is not None:
                task.cancel()
        await asyncio.gather(
            *(task for task in (interest_task, rubric_task) if task is not None),
            return_exceptions=True,
        )
        await asyncio.to_thread(
            jobs.mark_failed,
            owner_uid=owner_uid,
            project_id=project_id,
            job_id=job_id,
            message=f"Analysis failed: {exc}",
            code="ANALYZE_FAILED",
        )
        await asyncio.to_thread(
            analyses.finish_run,
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
    await asyncio.to_thread(
        jobs.update_progress,
        owner_uid=owner_uid,
        project_id=project_id,
        job_id=job_id,
        percent=_REVIEW_END_PERCENT,
        step="aggregating",
        message="Building the heatmap",
    )

    await asyncio.to_thread(
        jobs.update_progress,
        owner_uid=owner_uid,
        project_id=project_id,
        job_id=job_id,
        percent=_REVIEW_END_PERCENT,
        step="adjudicating",
        message="Checking serious findings against the footage",
    )
    editorial = EditorSummary(
        model=settings.model_editor or settings.model_reviewer, promptVersion=EDITOR_PROMPT_VERSION
    )
    adjudication = AdjudicatorSummary(
        model=settings.model_adjudicator or settings.model_reviewer,
        promptVersion=ADJUDICATOR_PROMPT_VERSION,
    )
    try:
        # Reserve the concurrently running interest pass conservatively before admitting checks.
        review_cost = sum(
            estimate_cost_usd(
                o.usage,
                input_price_per_mtok=settings.llm_input_price_per_mtok,
                output_price_per_mtok=settings.llm_output_price_per_mtok,
            )
            for o in outcomes
        )
        spent = await asyncio.to_thread(
            analyses.spent_usd,
            owner_uid=owner_uid,
            project_id=project_id,
            exclude_run_id=analysis_run_id,
        )
        prior_adjudicator_cost = await asyncio.to_thread(
            analyses.adjudicator_spent_usd,
            owner_uid=owner_uid,
            project_id=project_id,
            analysis_run_id=analysis_run_id,
        )
        interest_reserve = (
            estimate_cost_usd(
                LlmUsage(input_tokens=48_000, output_tokens=16_000),
                input_price_per_mtok=settings.llm_input_price_per_mtok,
                output_price_per_mtok=settings.llm_output_price_per_mtok,
            )
            if interest_task is not None
            else 0.0
        )

        prior_editor_cost = await asyncio.to_thread(
            analyses.editor_spent_usd,
            owner_uid=owner_uid,
            project_id=project_id,
            analysis_run_id=analysis_run_id,
        )

        async def reserve_editor(label: str) -> str | None:
            return await asyncio.to_thread(
                analyses.reserve_editor_call,
                owner_uid=owner_uid,
                project_id=project_id,
                analysis_run_id=analysis_run_id,
                label=label,
            )

        async def settle_editor(slot: str, usage: LlmUsage | None, error: str | None) -> None:
            await asyncio.to_thread(
                analyses.settle_editor_call,
                owner_uid=owner_uid,
                slot=slot,
                usage=usage,
                error=error,
            )

        rubric_findings, rubric_summary = (
            await rubric_task
            if rubric_task is not None
            else await run_rubric_review(
                llm,
                settings=settings,
                segments=segments,
                context=contexts[0],
                media=tuple(frame.media for c in contexts for frame in c.sampled_frames),
                budget_usd=settings.max_project_cost_usd
                - spent
                - review_cost
                - prior_adjudicator_cost
                - prior_editor_cost
                - interest_reserve,
                reserve_call=reserve_rubric,
                settle_call=settle_rubric,
            )
        )
        if rubric_summary.skippedCount:
            rubric_findings = [
                f
                for f in await asyncio.to_thread(
                    analyses.list_findings,
                    owner_uid=owner_uid,
                    project_id=project_id,
                    analysis_run_id=analysis_run_id,
                )
                if f.reviewerRunId == "rubric"
            ]
        await asyncio.to_thread(
            analyses.save_rubric_summary,
            owner_uid=owner_uid,
            project_id=project_id,
            analysis_run_id=analysis_run_id,
            summary=rubric_summary,
            findings=rubric_findings,
        )
        review_cost += await asyncio.to_thread(
            analyses.rubric_spent_usd,
            owner_uid=owner_uid,
            project_id=project_id,
            analysis_run_id=analysis_run_id,
        )
        findings.extend(rubric_findings)

        try:
            editorial = await edit_findings(
                findings,
                segments=segments,
                duration_ms=transcript.durationMs,
                llm=llm,
                settings=settings,
                budget_usd=settings.max_project_cost_usd
                - spent
                - review_cost
                - prior_adjudicator_cost
                - prior_editor_cost
                - interest_reserve,
                creator_context=(
                    f"Title: {video_title}\nBrief: {project_brief}\n"
                    f"Audience: {audience}\nPlatform: {platform}\n"
                    f"Persona: {persona_markdown[:1500]}"
                ),
                reserve_call=reserve_editor,
                settle_call=settle_editor,
            )
            await asyncio.to_thread(
                analyses.save_editorial,
                owner_uid=owner_uid,
                project_id=project_id,
                analysis_run_id=analysis_run_id,
                findings=findings,
                summary=editorial,
            )
        except Exception:  # noqa: BLE001 - editor persistence is optional
            logger.exception("analyze job %s: editor pass unavailable", job_id)
            try:
                findings = await asyncio.to_thread(
                    analyses.list_findings,
                    owner_uid=owner_uid,
                    project_id=project_id,
                    analysis_run_id=analysis_run_id,
                )
            except Exception:  # noqa: BLE001
                findings = [
                    f.model_copy(update={"editorial": None, "corroboratedBy": []}) for f in findings
                ]
        # Include durable uncertain charges on interrupted runs.
        editorial.costEstimateUsd = await asyncio.to_thread(
            analyses.editor_spent_usd,
            owner_uid=owner_uid,
            project_id=project_id,
            analysis_run_id=analysis_run_id,
        )

        async def reserve_call(kind: str, label: str, finding_limit: int) -> str | None:
            return await asyncio.to_thread(
                analyses.reserve_adjudicator_call,
                owner_uid=owner_uid,
                project_id=project_id,
                analysis_run_id=analysis_run_id,
                kind=kind,
                label=label,
                finding_limit=finding_limit,
            )

        async def settle_call(slot: str, usage: LlmUsage | None, error: str | None) -> None:
            await asyncio.to_thread(
                analyses.settle_adjudicator_call,
                owner_uid=owner_uid,
                slot=slot,
                usage=usage,
                error=error,
            )

        adjudication = await adjudicate(
            findings,
            segments=segments,
            llm=llm,
            settings=settings,
            toolkit=visual_tools,
            store=context_store,
            reserve_call=reserve_call,
            settle_call=settle_call,
            budget_usd=(
                settings.max_project_cost_usd
                - spent
                - review_cost
                - editorial.costEstimateUsd
                - prior_adjudicator_cost
                - interest_reserve
            ),
            creator_context=(
                f"Title: {video_title}\nBrief: {project_brief}\nAudience: {audience}\n"
                f"Platform: {platform}\nPersona: {persona_markdown[:1500]}"
            ),
        )
        await asyncio.to_thread(
            analyses.save_adjudication,
            owner_uid=owner_uid,
            project_id=project_id,
            analysis_run_id=analysis_run_id,
            findings=findings,
            summary=adjudication,
        )
    except Exception:  # noqa: BLE001 - verification is never a review dependency
        logger.exception("analyze job %s: adjudicator pass unavailable", job_id)
        # Build bins from what the creator can actually read after a partial write failure.
        try:
            findings = await asyncio.to_thread(
                analyses.list_findings,
                owner_uid=owner_uid,
                project_id=project_id,
                analysis_run_id=analysis_run_id,
            )
        except Exception:  # noqa: BLE001
            findings = [
                f.model_copy(update={"adjudication": None, "reconciliation": None})
                for f in findings
            ]
    library_cost_usd = await enrich_finding_library_links(
        analyses=analyses,
        owner_uid=owner_uid,
        project_id=project_id,
        analysis_run_id=analysis_run_id,
        findings=effective_findings(findings),
        transcript_text=" ".join(segment.text for segment in segments),
        llm=llm,
        settings=settings,
    )
    bins = aggregate_bins(findings, duration_ms=transcript.durationMs)
    summary = summarize_findings(findings)
    coverage = merge_coverage(
        {
            outcome.dimension: outcome.reviewed_spans
            for outcome in outcomes
            if outcome.status.value == "succeeded"
        },
        duration_ms=transcript.durationMs,
    )
    await asyncio.to_thread(
        analyses.save_bins,
        owner_uid=owner_uid,
        project_id=project_id,
        analysis_run_id=analysis_run_id,
        bins=bins,
    )
    interest_usage = LlmUsage()
    if interest_task is not None:
        try:
            prediction = await interest_task
        except Exception:  # noqa: BLE001 - the curve is an enhancement, never a dependency
            logger.exception("analyze job %s: interest curve failed", job_id)
            prediction = None
        if prediction is not None:
            curve, interest_usage = prediction
            curve = _link_findings(
                curve, effective_findings(findings), analysis_run_id=analysis_run_id
            )
            curve = curve.model_copy(
                update={
                    "costEstimateUsd": round(
                        estimate_cost_usd(
                            interest_usage,
                            input_price_per_mtok=settings.llm_input_price_per_mtok,
                            output_price_per_mtok=settings.llm_output_price_per_mtok,
                        ),
                        6,
                    )
                }
            )
            try:
                await asyncio.to_thread(
                    analyses.save_interest,
                    owner_uid=owner_uid,
                    project_id=project_id,
                    analysis_run_id=analysis_run_id,
                    curve=curve,
                )
            except Exception:  # noqa: BLE001
                logger.exception("analyze job %s: could not save interest curve", job_id)

    succeeded = [o for o in outcomes if o.status.value == "succeeded"]
    cost_usd = round(
        sum(
            estimate_cost_usd(
                outcome.usage,
                input_price_per_mtok=settings.llm_input_price_per_mtok,
                output_price_per_mtok=settings.llm_output_price_per_mtok,
            )
            for outcome in outcomes
        )
        + await asyncio.to_thread(
            analyses.rubric_spent_usd,
            owner_uid=owner_uid,
            project_id=project_id,
            analysis_run_id=analysis_run_id,
        )
        + editorial.costEstimateUsd
        + adjudication.costEstimateUsd
        + library_cost_usd
        + estimate_cost_usd(
            interest_usage,
            input_price_per_mtok=settings.llm_input_price_per_mtok,
            output_price_per_mtok=settings.llm_output_price_per_mtok,
        ),
        6,
    )
    failed_count = sum(o.status.value == "failed" or o.error is not None for o in outcomes)
    if not succeeded:
        status = AnalysisRunStatus.failed
    elif failed_count:
        status = AnalysisRunStatus.partial_failure
    else:
        status = AnalysisRunStatus.ready
    error = (
        {
            "code": "SOME_REVIEWERS_FAILED",
            "message": f"{failed_count} reviewer(s) could not review the entire video.",
        }
        if failed_count
        else None
    )

    run_model = await asyncio.to_thread(
        analyses.finish_run,
        owner_uid=owner_uid,
        project_id=project_id,
        analysis_run_id=analysis_run_id,
        status=status,
        summary=summary,
        cost_usd=cost_usd,
        completed_dimensions=[o.dimension for o in succeeded],
        error=error,
        coverage=coverage,
    )
    if status is AnalysisRunStatus.failed:
        await asyncio.to_thread(
            jobs.mark_failed,
            owner_uid=owner_uid,
            project_id=project_id,
            job_id=job_id,
            message="Every reviewer failed. Nothing to show for this run.",
            code="ANALYZE_FAILED",
        )
    else:
        await asyncio.to_thread(
            jobs.mark_succeeded,
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
            message=("Completed" if status is AnalysisRunStatus.ready else "Completed with gaps"),
        )
    await asyncio.to_thread(
        _publish,
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


async def _predict_interest(
    llm: LlmProvider,
    settings: Settings,
    *,
    segments: list[SegmentRef],
    duration_ms: int,
    title: str,
    language: str,
) -> tuple[InterestCurve, LlmUsage] | None:
    """Predict the relative-interest curve for this transcript, or None when unavailable.

    The Gemini signal pass runs only when the bundled model chose it in training and the
    configured model is the one it was trained on; otherwise, or when the pass fails, the
    transcript-only head runs instead.
    """
    model = load_model()
    if model is None or duration_ms <= 0:
        return None
    words = words_from_segments(
        [(segment.start_ms, segment.end_ms, segment.text) for segment in segments]
    )
    usage = LlmUsage()
    signal_rows = None
    if not model.uses_signals:
        pass
    elif settings.model_interest_signals == model.signal_model:
        try:
            signals = await score_windows(
                llm,
                model=settings.model_interest_signals,
                texts=bin_texts(words, duration_ms),
                title=title,
                language=language,
            )
            signal_rows, usage = signals.rows, signals.usage
        except Exception:  # noqa: BLE001 - fall back to the transcript-only head
            logger.warning("interest signal pass failed; using transcript-only model")
    else:
        logger.warning(
            "interest signals model %s differs from trained %s; using transcript-only model",
            settings.model_interest_signals,
            model.signal_model,
        )
    curve = build_curve(model, words=words, duration_ms=duration_ms, signal_rows=signal_rows)
    metrics = model.metrics
    calibration = None
    if metrics:
        try:
            calibration = InterestCalibration(
                label=str(metrics.get("label") or ""),
                videos=int(metrics.get("videos") or 0),
                channels=int(metrics.get("channels") or 0),
                testVideos=int(metrics.get("testVideos") or 0),
                heldOutSpearman=float(
                    metrics.get(
                        "heldOutSpearman"
                        if curve.feature_source == "transcript+gemini"
                        else "transcriptFallbackSpearman",
                        0.0,
                    )
                ),
                positionBaselineSpearman=float(metrics.get("positionBaselineSpearman") or 0.0),
                liftSpearman=float(
                    metrics.get(
                        "liftSpearman"
                        if curve.feature_source == "transcript+gemini"
                        else "transcriptLiftSpearman",
                        0.0,
                    )
                ),
                peakPrecision=float(metrics.get("peakPrecision") or 0.0),
                dipPrecision=float(metrics.get("dipPrecision") or 0.0),
                trainedAt=str(metrics.get("trainedAt") or ""),
            )
        except (TypeError, ValueError):
            calibration = None

    def moment(item: CurveMoment) -> InterestMoment:
        return InterestMoment(
            kind="peak" if item.kind == "peak" else "dip",
            startMs=item.start_ms,
            endMs=item.end_ms,
            value=item.value,
            drivers=list(item.drivers),
        )

    return (
        InterestCurve(
            analysisRunId="",
            status="ready",
            modelVersion=model.version,
            featureSource=(
                "transcript+gemini" if curve.feature_source == "transcript+gemini" else "transcript"
            ),
            durationMs=duration_ms,
            points=[
                InterestPoint(
                    startMs=point.start_ms,
                    endMs=point.end_ms,
                    value=point.value,
                    baseline=point.baseline,
                    driversUp=list(point.drivers_up),
                    driversDown=list(point.drivers_down),
                    signals=point.signals,
                )
                for point in curve.points
            ],
            peaks=[moment(item) for item in curve.peaks],
            dips=[moment(item) for item in curve.dips],
            calibration=calibration,
            createdAt=datetime.now(UTC),
        ),
        usage,
    )


_SEVERITY_RANK = {severity: rank for rank, severity in enumerate(Severity)}


def _link_findings(
    curve: InterestCurve, findings: list[Finding], *, analysis_run_id: str
) -> InterestCurve:
    """Attach overlapping findings to each peak and dip, most severe first (at most six).

    Dips link to problems, peaks to strengths and problems alike, so a dip next to a
    pacing finding explains itself.
    """

    def overlapping(item: InterestMoment) -> InterestMoment:
        hits = [
            finding
            for finding in findings
            if finding.startMs < item.endMs
            and finding.endMs > item.startMs
            and (item.kind == "peak" or finding.severity is not Severity.none)
        ]
        hits.sort(key=lambda f: (-_SEVERITY_RANK[f.severity], f.startMs))
        return item.model_copy(update={"findingIds": [f.findingId for f in hits[:6]]})

    return curve.model_copy(
        update={
            "analysisRunId": analysis_run_id,
            "peaks": [overlapping(item) for item in curve.peaks],
            "dips": [overlapping(item) for item in curve.dips],
        }
    )


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
        analyses.save_findings(
            owner_uid=owner_uid,
            project_id=project_id,
            analysis_run_id=analysis_run_id,
            findings=outcome.findings,
        )
        analyses.save_reviewer_outcome(
            owner_uid=owner_uid,
            project_id=project_id,
            analysis_run_id=analysis_run_id,
            outcome=outcome,
        )
    except Exception:  # noqa: BLE001 - a write failure must not lose the other reviewers
        logger.exception("failed to persist %s reviewer result", outcome.dimension.value)
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
) -> tuple[str, str, str]:
    """(video title, thumbnail concept, creator brief) for the reviewers.

    The project name doubles as the video title. Never a hard dependency.
    """
    try:
        project = analyses.client.get_document(project_path(owner_uid, project_id)) or {}
    except Exception:  # noqa: BLE001
        return "", "", ""
    if project.get("ownerUid") != owner_uid:
        return "", "", ""
    title = str(project.get("name") or "").strip()[:200]
    thumbnail = str(project.get("thumbnailConcept") or "").strip()[:500]
    brief = str(project.get("description") or "").strip()[:2000]
    return title, thumbnail, brief


async def _add_sampled_frames(
    contexts: list[ReviewContext],
    toolkit: MediaToolkit,
    store: GcsContextArtifactStore | None,
) -> list[ReviewContext]:
    """Extract at most six shared stills; failures retain a usable transcript review.

    No extra model call. Each frame is stored once under this run's project prefix,
    and attached only to reviewers of the interval that contains its timestamp.
    """
    if not contexts or toolkit.duration_ms <= 0:
        return contexts
    duration = toolkit.duration_ms
    last = max(0, duration - 1)
    timestamps = {min(1000, last), duration // 2, max(0, duration - 1000)}
    if duration > 60_000:
        timestamps.update({12_000, duration // 3, duration * 2 // 3})
    semaphore = asyncio.Semaphore(2)

    async def sample(index: int, timestamp: int) -> ReviewFrame | None:
        async with semaphore:
            try:
                part = await toolkit.extract_frame(timestamp)
            except Exception:  # noqa: BLE001 - evidence never gates the review
                logger.warning("shared review frame at %d ms unavailable", timestamp)
                return None
            path = ""
            if store is not None:
                try:
                    path = await asyncio.to_thread(
                        store.save,
                        part,
                        reviewer_run_id="shared",
                        tool="extract_frame",
                        index=index,
                    )
                except Exception:  # noqa: BLE001 - model can still inspect the frame
                    logger.warning("shared review frame at %d ms could not be stored", timestamp)
            return ReviewFrame(timestamp_ms=timestamp, media=part, content_path=path)

    sampled = await asyncio.gather(*(sample(i, t) for i, t in enumerate(sorted(timestamps))))
    frames = [frame for frame in sampled if frame is not None]
    return [
        replace(
            context,
            sampled_frames=tuple(
                frame
                for frame in frames
                if context.review_start_ms <= frame.timestamp_ms < context.review_end_ms
            ),
        )
        for context in contexts
    ]


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
        asset = analyses.client.get_document(asset_path(owner_uid, project_id, str(asset_id)))
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
    prefix = f"{project_object_prefix(owner_uid, project_id)}review-context/{analysis_run_id}/"
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
