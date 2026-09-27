"""Transcription worker: consume a queued `transcribe` job and produce a transcript.

Pipeline (per `docs/technical-design/backend-plan.md` section 7):

video.uploaded -> transcribe job queued -> STT V2 batch recognition (`chirp_3`, GCS input)
-> normalize words -> segment -> canonical JSON + VTT + SRT to GCS
-> transcript + segments to Firestore -> project ready -> job succeeded
-> publish transcript.ready.

Idempotent: a job that already reached a terminal state (`succeeded`/`failed`/`cancelled`)
is left untouched so retried Pub/Sub deliveries converge.
"""

import asyncio
import logging
import os
from typing import Any

from fastapi import BackgroundTasks

from app.config import Settings, get_settings
from app.errors import NotFoundError
from app.events import build_event, topic_for_event
from app.providers import get_providers
from app.providers.base import LlmProvider
from app.providers.stt import SttProvider
from app.realtime.events import emit_transcript_ready
from app.schemas.jobs import JobStatus
from app.services.asset_service import AssetService
from app.services.firestore_service import (
    FirestoreClient,
    asset_path,
    get_firestore_client,
    project_object_prefix,
)
from app.services.job_service import JobService
from app.services.media import extract_aac_track, mux_m4a
from app.services.project_service import ProjectService
from app.services.pubsub_service import PubSubClient, get_pubsub_client
from app.services.storage_service import StorageClient, get_storage_client
from app.services.transcript_repair import repair_transcript
from app.services.transcript_service import (
    TranscriptService,
    build_segments,
    normalize_words,
    sanitize_word_timings,
)
from app.services.video_tools import ffmpeg_available, probe_duration_ms

logger = logging.getLogger(__name__)

TERMINAL_STATUSES = frozenset(
    {JobStatus.succeeded.value, JobStatus.failed.value, JobStatus.cancelled.value}
)


async def run_transcribe(
    *,
    owner_uid: str,
    project_id: str,
    job_id: str,
    firestore: FirestoreClient,
    jobs: JobService,
    projects: ProjectService,
    assets: AssetService,
    transcripts: TranscriptService,
    stt: SttProvider,
    llm: LlmProvider,
    settings: Settings,
    pubsub: PubSubClient | None = None,
) -> str | None:
    """Run one transcription job. Returns the transcript id, or None if skipped/failed."""
    try:
        job = jobs.load_for_worker(owner_uid=owner_uid, project_id=project_id, job_id=job_id)
    except NotFoundError:
        logger.warning("transcribe job %s not found; skipping", job_id)
        return None

    if job.get("status") in TERMINAL_STATUSES:
        logger.info("transcribe job %s already %s; skipping", job_id, job.get("status"))
        return _active_transcript_id(firestore, owner_uid, project_id)

    asset_id = (job.get("input") or {}).get("assetId")
    if not asset_id:
        jobs.mark_failed(
            owner_uid=owner_uid,
            project_id=project_id,
            job_id=job_id,
            message="Transcription job is missing its asset id.",
        )
        projects.mark_failed(
            owner_uid=owner_uid,
            project_id=project_id,
            message="Transcription failed: missing asset.",
        )
        return None

    asset = firestore.get_document(asset_path(owner_uid, project_id, asset_id))
    if asset is None or asset.get("ownerUid") != owner_uid:
        jobs.mark_failed(
            owner_uid=owner_uid,
            project_id=project_id,
            job_id=job_id,
            message="Source asset not found.",
        )
        projects.mark_failed(
            owner_uid=owner_uid,
            project_id=project_id,
            message="Transcription failed: source video missing.",
        )
        return None

    jobs.mark_running(
        owner_uid=owner_uid,
        project_id=project_id,
        job_id=job_id,
        step="speech_to_text",
        message="Transcribing audio",
    )
    firestore.update_document(asset_path(owner_uid, project_id, asset_id), {"status": "processing"})

    # Chirp 3 does language-agnostic transcription: "auto" lets the service identify the spoken
    # language (English, Hindi, Hinglish, ...) and report it back, which we persist.
    language_codes = ["auto"]
    gcs_uri = stt.gcs_uri_for(asset["storagePath"])
    try:
        response = await stt.transcribe(
            gcs_uri=gcs_uri,
            language_codes=language_codes,
            model=settings.model_stt,
            enable_diarization=settings.stt_enable_diarization,
        )
    except Exception as exc:  # noqa: BLE001 - worker must record provider failures
        logger.warning("transcribe job %s: STT failed (%s); trying normalized audio", job_id, exc)
        jobs.update_progress(
            owner_uid=owner_uid,
            project_id=project_id,
            job_id=job_id,
            percent=30,
            step="speech_to_text",
            message="Retrying with normalized audio",
        )
        retry_response = await _retry_with_normalized_audio(
            storage_path=asset["storagePath"],
            owner_uid=owner_uid,
            project_id=project_id,
            job_id=job_id,
            stt=stt,
            transcripts=transcripts,
            jobs=jobs,
            settings=settings,
        )
        if retry_response is None:
            logger.exception("transcribe job %s: STT failed", job_id)
            firestore.update_document(
                asset_path(owner_uid, project_id, asset_id), {"status": "failed"}
            )
            jobs.mark_failed(
                owner_uid=owner_uid,
                project_id=project_id,
                job_id=job_id,
                message=f"Speech recognition failed: {exc}",
            )
            # Persist the concrete reason on the project too: the UI loses the job id on
            # reload and used to fall back to a generic message, so the reason vanished.
            projects.mark_failed(
                owner_uid=owner_uid,
                project_id=project_id,
                message=_failure_message(exc),
            )
            return None
        response = retry_response
        logger.info("transcribe job %s: normalized-audio retry accepted", job_id)

    media_duration_ms = await _probe_media_duration(
        storage=transcripts.storage,
        storage_path=asset["storagePath"],
        settings=settings,
        job_id=job_id,
    )
    words = normalize_words(response)
    # Chirp sometimes emits offsets past the end of the video; drop those before segmenting.
    words, duration_ms = sanitize_word_timings(words, media_duration_ms)
    language = response.get("language") or _project_language(firestore, owner_uid, project_id)
    jobs.update_progress(
        owner_uid=owner_uid,
        project_id=project_id,
        job_id=job_id,
        percent=70,
        step="segmenting",
        message="Segmenting transcript",
    )
    segments = build_segments(words)

    # Post-Chirp cleanup: fix obvious recognition errors and infer speaker turns. Best-effort
    # by design (the pass never raises), so raw STT output is the floor, never lost.
    speaker_labels: dict[str, str] = {}
    if settings.transcript_repair_enabled and segments:
        jobs.update_progress(
            owner_uid=owner_uid,
            project_id=project_id,
            job_id=job_id,
            percent=80,
            step="polishing",
            message="Checking the transcript",
        )
        repair = await repair_transcript(
            segments,
            language=language,
            llm=llm,
            model=settings.model_transcript_repair,
            max_chars=settings.transcript_repair_max_chars,
        )
        segments = repair.segments
        speaker_labels = repair.speaker_labels

    transcript_id = transcripts.save(
        owner_uid=owner_uid,
        project_id=project_id,
        source_asset_id=asset_id,
        language=language,
        words=words,
        segments=segments,
        speaker_labels=speaker_labels,
        duration_ms=duration_ms,
    )
    firestore.update_document(
        asset_path(owner_uid, project_id, asset_id), {"status": "ready", "durationMs": duration_ms}
    )
    projects.mark_transcript_ready(
        owner_uid=owner_uid,
        project_id=project_id,
        transcript_id=transcript_id,
        duration_ms=duration_ms,
        word_count=len(words),
    )
    jobs.mark_succeeded(
        owner_uid=owner_uid,
        project_id=project_id,
        job_id=job_id,
        output={"artifactIds": [], "storagePaths": [], "transcriptId": transcript_id},
        message="Completed" if words else "Completed — no speech detected",
    )
    _publish_transcript_ready(
        pubsub,
        owner_uid=owner_uid,
        project_id=project_id,
        job_id=job_id,
        transcript_id=transcript_id,
        language=language,
        duration_ms=duration_ms,
        word_count=len(words),
    )
    logger.info(
        "transcribe job %s done: %d words in %d segments",
        job_id,
        len(words),
        len(segments),
    )
    return transcript_id


# Containers worth re-muxing when STT rejects them. The provider already routes these
# through explicit decoding, so a failure here means the container itself confused
# the importer — not the codec, which the fallback preserves untouched.
_NORMALIZE_EXTENSIONS = frozenset({".mp4", ".mov", ".m4v", ".m4a"})


def _failure_message(exc: BaseException) -> str:
    """User-facing reason stored on the project so a failure survives a page reload."""
    detail = str(exc).strip()
    if not detail:
        return "Transcription failed. Retry from the workspace."
    return f"Transcription failed: {detail}"


async def _probe_media_duration(
    *, storage: StorageClient, storage_path: str, settings: Settings, job_id: str
) -> int | None:
    """Real media duration via ffprobe on a signed URL, or None to estimate from words."""
    if not ffmpeg_available(settings.ffprobe_path):
        logger.info(
            "transcribe job %s: ffprobe (%s) unavailable; estimating duration",
            job_id,
            settings.ffprobe_path,
        )
        return None
    try:
        source = storage.signed_download_url(storage_path, expires_seconds=900)
    except Exception:  # noqa: BLE001 - the length probe is best-effort
        logger.warning(
            "transcribe job %s: cannot sign the source for a length probe",
            job_id,
            exc_info=True,
        )
        return None
    duration = await asyncio.to_thread(
        probe_duration_ms, source, ffprobe_path=settings.ffprobe_path
    )
    if duration:
        logger.info("transcribe job %s: media duration %.1fs", job_id, duration / 1000)
    return duration


async def _retry_with_normalized_audio(
    *,
    storage_path: str,
    owner_uid: str,
    project_id: str,
    job_id: str,
    stt: SttProvider,
    transcripts: TranscriptService,
    jobs: JobService,
    settings: Settings,
) -> dict[str, Any] | None:
    """Re-mux a rejected container's AAC track into a clean `.m4a` and retry STT once.

    Returns the STT response, or None when the file is not a normalizable MP4-family
    container (caller keeps the original STT error). The temp object lives under the
    project prefix, so project deletion covers it even if cleanup below is skipped.
    """
    if os.path.splitext(storage_path)[1].lower() not in _NORMALIZE_EXTENSIONS:
        return None
    try:
        source = transcripts.storage.download_bytes(storage_path)
    except Exception:  # noqa: BLE001 - fall through to the original STT error
        logger.warning("transcribe job %s: cannot download source for retry", job_id)
        return None
    if len(source) > settings.max_upload_size_bytes:
        logger.warning("transcribe job %s: source too large to normalize", job_id)
        return None
    track = extract_aac_track(source)
    if track is None:
        logger.warning("transcribe job %s: no AAC-LC track to normalize", job_id)
        return None
    tmp_path = f"{project_object_prefix(owner_uid, project_id)}transcribe-tmp/{job_id}.m4a"
    try:
        transcripts.storage.upload_bytes(
            tmp_path, mux_m4a(track), content_type="audio/mp4"
        )
    except Exception:  # noqa: BLE001 - fall through to the original STT error
        logger.warning("transcribe job %s: cannot stage normalized audio", job_id)
        return None
    try:
        return await stt.transcribe(
            gcs_uri=stt.gcs_uri_for(tmp_path),
            language_codes=["auto"],
            model=settings.model_stt,
            enable_diarization=settings.stt_enable_diarization,
        )
    except Exception:  # noqa: BLE001 - the retry failed too; keep the first error
        logger.warning("transcribe job %s: normalized-audio retry failed", job_id)
        return None
    finally:
        try:
            transcripts.storage.delete_prefix(tmp_path)
        except Exception:  # noqa: BLE001 - temp is under the project prefix; delete covers it
            logger.warning("transcribe job %s: cannot clean up normalized audio", job_id)


def _publish_transcript_ready(
    pubsub: PubSubClient | None,
    *,
    owner_uid: str,
    project_id: str,
    job_id: str,
    transcript_id: str,
    language: str,
    duration_ms: int,
    word_count: int,
) -> None:
    """Announce the next pipeline step. Best-effort: the transcript is already persisted."""
    # Realtime (browser) announcement is independent of Pub/Sub, which feeds
    # other infrastructure consumers and may be unconfigured locally.
    emit_transcript_ready(
        owner_uid,
        project_id,
        transcript_id=transcript_id,
        job_id=job_id,
        language=language,
        duration_ms=duration_ms,
    )
    if pubsub is None:
        return
    event = build_event(
        event_type="transcript.ready",
        owner_uid=owner_uid,
        project_id=project_id,
        job_id=job_id,
        payload={
            "transcriptId": transcript_id,
            "language": language,
            "durationMs": duration_ms,
            "wordCount": word_count,
        },
    )
    try:
        pubsub.publish(topic=topic_for_event("transcript.ready"), event=event)
    except Exception:  # noqa: BLE001 - a publish failure must not fail a finished transcript
        logger.exception("transcribe job %s: failed to publish transcript.ready", job_id)


# STT wants a BCP-47 tag. The app stores bare codes ("en", "hi", ...), so map the ones the
# product offers to a full tag; unknown codes pass through and are validated by the service.
_LANGUAGE_TAGS = {
    "en": "en-US",
    "hi": "hi-IN",
    "mr": "mr-IN",
    "ta": "ta-IN",
    "te": "te-IN",
    "bn": "bn-IN",
    "es": "es-ES",
}


def _project_language(firestore: FirestoreClient, owner_uid: str, project_id: str) -> str:
    """Fallback transcript language when STT does not report a detected one."""
    from app.services.firestore_service import project_path

    project = firestore.get_document(project_path(owner_uid, project_id)) or {}
    return _bcp47(str(project.get("primaryLanguage") or "en"))


def _bcp47(code: str) -> str:
    return code if "-" in code else _LANGUAGE_TAGS.get(code, code)


def _active_transcript_id(
    firestore: FirestoreClient, owner_uid: str, project_id: str
) -> str | None:
    from app.services.firestore_service import project_path

    project = firestore.get_document(project_path(owner_uid, project_id)) or {}
    return project.get("activeTranscriptId")


def build_worker_services(
    *,
    firestore: FirestoreClient,
    jobs: JobService,
    projects: ProjectService,
    assets: AssetService,
    transcripts: TranscriptService,
    stt: SttProvider,
    llm: LlmProvider,
    settings: Settings,
    pubsub: PubSubClient | None = None,
) -> dict[str, Any]:
    """Bundle worker deps for call sites (API-triggered inline run, Pub/Sub handler)."""
    return {
        "firestore": firestore,
        "jobs": jobs,
        "projects": projects,
        "assets": assets,
        "transcripts": transcripts,
        "stt": stt,
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
    projects = ProjectService(firestore)
    return build_worker_services(
        firestore=firestore,
        jobs=jobs,
        projects=projects,
        assets=AssetService(
            firestore,
            projects=projects,
            jobs=jobs,
            storage=storage,
            settings=settings,
        ),
        transcripts=TranscriptService(firestore, storage=storage),
        stt=get_providers().stt,
        llm=get_providers().llm,
        settings=settings,
        pubsub=get_pubsub_client(),
    )


def transcribe_after_response(
    background_tasks: BackgroundTasks,
    *,
    owner_uid: str,
    project_id: str,
    job_id: str,
) -> None:
    """Run the transcription worker after the HTTP response is sent.

    `POST /assets/{id}/complete` is authoritative for the user-visible state and schedules the
    work here for a fast response; the GCS `object finalized` -> Pub/Sub path is the trigger of
    record and converges on the same idempotent job. Builds live dependencies, so call sites
    that need fakes (tests) must inject their own scheduler instead.
    """
    background_tasks.add_task(
        run_transcribe,
        owner_uid=owner_uid,
        project_id=project_id,
        job_id=job_id,
        **live_worker_dependencies(),
    )
