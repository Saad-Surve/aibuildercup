"""Caption burn-in worker: render a styled ASS track over the project's source video.

Pipeline: a `caption_render` job is queued by the API -> build an ASS document from the
transcript + `CaptionStyle` -> FFmpeg overlays it with libass (`ass` filter, bundled fonts)
-> the burned MP4 and the ASS are uploaded under the project prefix -> render + job marked
ready. The job is idempotent: a terminal job is left untouched, and a render that is already
ready is not re-encoded.

FFmpeg reads the source straight from a short-lived signed URL (no download of the original),
and writes the result to a temp file that is streamed back to Cloud Storage.
"""

import asyncio
import logging
import os
import shutil
import tempfile
import time
from collections.abc import Callable
from typing import Any

from app.config import Settings, get_settings
from app.errors import NotFoundError
from app.schemas.captions import CaptionRenderStatus, CaptionStyle
from app.schemas.jobs import JobStatus
from app.services.caption_service import CaptionRenderService
from app.services.caption_styles import FONTS_DIR, build_ass
from app.services.firestore_service import (
    FirestoreClient,
    asset_path,
    get_firestore_client,
)
from app.services.job_service import JobService
from app.services.project_service import ProjectService
from app.services.source_media import stage_source
from app.services.storage_service import StorageClient, get_storage_client
from app.services.transcript_service import TranscriptService
from app.services.video_tools import (
    VideoToolError,
    ffmpeg_available,
    run_ffmpeg_with_progress,
)

logger = logging.getLogger(__name__)

TERMINAL_STATUSES = frozenset(
    {JobStatus.succeeded.value, JobStatus.failed.value, JobStatus.cancelled.value}
)

#: Bounded encode settings: fast enough for a demo, good enough for a feed.
_ENCODE_TIMEOUT_MIN_SECONDS = 300
_ENCODE_TIMEOUT_MAX_SECONDS = 3600

#: Encode progress is mapped into this slice of the job's percent, so the UI moves
#: through the FFmpeg pass instead of sitting on one value for the whole encode.
_ENCODE_PERCENT_START = 35
_ENCODE_PERCENT_END = 85
#: Minimum gap between persisted progress writes; FFmpeg reports far more often than
#: the UI or Firestore needs.
_PROGRESS_MIN_INTERVAL_SECONDS = 1.5


def _filter_value(value: str) -> str:
    """Quote a path for an FFmpeg filtergraph option value."""
    return "'" + value.replace("'", "'\\''") + "'"


def _encode_timeout(duration_ms: int) -> int:
    seconds = max(0, int(duration_ms or 0)) / 1000
    # Allow roughly 4x realtime; clamp so a runaway encode cannot hang a worker forever.
    return int(
        max(
            _ENCODE_TIMEOUT_MIN_SECONDS,
            min(_ENCODE_TIMEOUT_MAX_SECONDS, seconds * 4),
        )
    )


def _encode_progress_reporter(
    jobs: JobService,
    *,
    owner_uid: str,
    project_id: str,
    job_id: str,
) -> Callable[[float], None]:
    """Build an FFmpeg `on_progress` hook that advances the job through the encode.

    The callback runs on the FFmpeg reader thread, so it must never raise into the
    encoder; a failed progress write is logged and ignored. Writes are throttled by
    percent step and a minimum interval to keep Firestore traffic sane.
    """
    span = max(1, _ENCODE_PERCENT_END - _ENCODE_PERCENT_START)
    state = {"percent": _ENCODE_PERCENT_START, "at": 0.0}

    def report(fraction: float) -> None:
        clamped = min(1.0, max(0.0, fraction))
        percent = _ENCODE_PERCENT_START + int(round(clamped * span))
        now = time.monotonic()
        if percent <= state["percent"] or now - state["at"] < _PROGRESS_MIN_INTERVAL_SECONDS:
            return
        state["percent"] = percent
        state["at"] = now
        try:
            jobs.update_progress(
                owner_uid=owner_uid,
                project_id=project_id,
                job_id=job_id,
                percent=percent,
                step="rendering",
                message="Burning captions onto the video",
            )
        except Exception:  # noqa: BLE001 - progress must never fail the render
            logger.warning("caption render: progress update failed", exc_info=True)

    return report


def _ffmpeg_command(
    *,
    ffmpeg_path: str,
    source: str,
    ass_path: str,
    out_path: str,
) -> list[str]:
    filter_graph = (
        f"ass=filename={_filter_value(ass_path)}"
        f":fontsdir={_filter_value(str(FONTS_DIR))}"
    )
    return [
        ffmpeg_path,
        "-hide_banner",
        "-loglevel",
        "error",
        "-nostdin",
        "-y",
        "-i",
        source,
        "-map",
        "0:v:0",
        "-map",
        "0:a:0?",
        "-vf",
        filter_graph,
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-crf",
        "22",
        "-pix_fmt",
        "yuv420p",
        "-c:a",
        "aac",
        "-b:a",
        "160k",
        "-movflags",
        "+faststart",
        out_path,
    ]


async def run_caption_render(
    *,
    owner_uid: str,
    project_id: str,
    job_id: str,
    firestore: FirestoreClient,
    jobs: JobService,
    projects: ProjectService,
    captions: CaptionRenderService,
    transcripts: TranscriptService,
    storage: StorageClient,
    settings: Settings,
) -> str | None:
    """Run one caption render. Returns the render id, or None if skipped/failed."""
    try:
        job = jobs.load_for_worker(
            owner_uid=owner_uid, project_id=project_id, job_id=job_id
        )
    except NotFoundError:
        logger.warning("caption render job %s not found; skipping", job_id)
        return None

    if job.get("status") in TERMINAL_STATUSES:
        logger.info(
            "caption render job %s already %s; skipping", job_id, job.get("status")
        )
        return (job.get("input") or {}).get("captionRenderId")

    caption_render_id = (job.get("input") or {}).get("captionRenderId")
    if not caption_render_id:
        jobs.mark_failed(
            owner_uid=owner_uid,
            project_id=project_id,
            job_id=job_id,
            message="Caption render job is missing its render id.",
            code="CAPTION_RENDER_FAILED",
        )
        return None

    render = captions.load(
        owner_uid=owner_uid,
        project_id=project_id,
        caption_render_id=caption_render_id,
    )
    if render is None:
        jobs.mark_failed(
            owner_uid=owner_uid,
            project_id=project_id,
            job_id=job_id,
            message="Caption render record not found.",
            code="CAPTION_RENDER_FAILED",
        )
        return None

    if render.get("status") == CaptionRenderStatus.ready.value:
        jobs.mark_succeeded(
            owner_uid=owner_uid,
            project_id=project_id,
            job_id=job_id,
            output={
                "artifactIds": [],
                "storagePaths": [render.get("storagePath")] if render.get("storagePath") else [],
                "captionRenderId": caption_render_id,
            },
            message="Already rendered",
        )
        return caption_render_id

    try:
        await _render(
            owner_uid=owner_uid,
            project_id=project_id,
            job_id=job_id,
            caption_render_id=caption_render_id,
            render=render,
            firestore=firestore,
            jobs=jobs,
            captions=captions,
            transcripts=transcripts,
            storage=storage,
            settings=settings,
        )
    except Exception as exc:  # noqa: BLE001 - one catch marks both records failed
        logger.exception("caption render job %s failed", job_id)
        message = _failure_message(exc)
        try:
            captions.mark_failed(
                owner_uid=owner_uid,
                project_id=project_id,
                caption_render_id=caption_render_id,
                code="CAPTION_RENDER_FAILED",
                message=message,
            )
        except Exception:  # noqa: BLE001 - job failure is the primary signal
            logger.exception("caption render %s: could not mark failed", caption_render_id)
        jobs.mark_failed(
            owner_uid=owner_uid,
            project_id=project_id,
            job_id=job_id,
            message=message,
            code="CAPTION_RENDER_FAILED",
        )
        return None
    return caption_render_id


async def _render(
    *,
    owner_uid: str,
    project_id: str,
    job_id: str,
    caption_render_id: str,
    render: dict[str, Any],
    firestore: FirestoreClient,
    jobs: JobService,
    captions: CaptionRenderService,
    transcripts: TranscriptService,
    storage: StorageClient,
    settings: Settings,
) -> None:
    if not ffmpeg_available(settings.ffmpeg_path):
        raise VideoToolError(
            f"ffmpeg ({settings.ffmpeg_path}) is not available on this server"
        )

    jobs.mark_running(
        owner_uid=owner_uid,
        project_id=project_id,
        job_id=job_id,
        step="preparing",
        message="Preparing captions",
    )
    captions.mark_rendering(
        owner_uid=owner_uid,
        project_id=project_id,
        caption_render_id=caption_render_id,
    )

    source_asset_id = render.get("sourceAssetId")
    if not source_asset_id:
        raise VideoToolError("The render has no source video.")
    asset = firestore.get_document(asset_path(owner_uid, project_id, str(source_asset_id)))
    if asset is None or asset.get("ownerUid") != owner_uid:
        raise VideoToolError("The source video is missing.")
    source_path = str(asset.get("storagePath") or "")
    if not source_path or not storage.object_exists(source_path):
        raise VideoToolError("The source video is missing from storage.")

    transcript_id = render.get("sourceTranscriptId")
    if not transcript_id:
        raise VideoToolError("The render has no source transcript.")
    transcript = transcripts.get_by_id(
        owner_uid=owner_uid, project_id=project_id, transcript_id=str(transcript_id)
    )
    if not transcript.segments:
        raise VideoToolError("The transcript has no segments to burn.")

    style = _style_from(render)
    segments = [
        {
            "startMs": segment.startMs,
            "endMs": segment.endMs,
            "text": segment.text,
            "speaker": segment.speaker,
        }
        for segment in transcript.segments
    ]

    video_object, ass_object = captions.target_paths(
        owner_uid=owner_uid,
        project_id=project_id,
        caption_render_id=caption_render_id,
    )

    tmpdir = tempfile.mkdtemp(prefix="caption-render-")
    try:
        source_ref, width, height, duration_ms = await stage_source(
            storage=storage,
            source_path=source_path,
            tmpdir=tmpdir,
            settings=settings,
            fallback_duration_ms=transcript.durationMs,
        )
        ass_text = build_ass(
            segments,
            style,
            width=width,
            height=height,
            speaker_labels=transcript.speakerLabels,
        )
        ass_path = os.path.join(tmpdir, "captions.ass")
        out_path = os.path.join(tmpdir, "captioned.mp4")
        with open(ass_path, "w", encoding="utf-8") as handle:
            handle.write(ass_text)

        jobs.update_progress(
            owner_uid=owner_uid,
            project_id=project_id,
            job_id=job_id,
            percent=_ENCODE_PERCENT_START,
            step="rendering",
            message="Burning captions onto the video",
        )
        args = _ffmpeg_command(
            ffmpeg_path=settings.ffmpeg_path,
            source=source_ref,
            ass_path=ass_path,
            out_path=out_path,
        )
        await asyncio.to_thread(
            run_ffmpeg_with_progress,
            args,
            timeout_seconds=_encode_timeout(duration_ms),
            duration_seconds=max(0.0, duration_ms / 1000),
            on_progress=_encode_progress_reporter(
                jobs,
                owner_uid=owner_uid,
                project_id=project_id,
                job_id=job_id,
            ),
        )
        if not os.path.exists(out_path) or os.path.getsize(out_path) == 0:
            raise VideoToolError("ffmpeg produced an empty video.")

        jobs.update_progress(
            owner_uid=owner_uid,
            project_id=project_id,
            job_id=job_id,
            percent=_ENCODE_PERCENT_END,
            step="uploading",
            message="Saving the captioned video",
        )
        size_bytes = os.path.getsize(out_path)
        storage.upload_from_filename(
            ass_object, ass_path, content_type="text/plain"
        )
        storage.upload_from_filename(
            video_object, out_path, content_type="video/mp4"
        )
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)

    captions.mark_ready(
        owner_uid=owner_uid,
        project_id=project_id,
        caption_render_id=caption_render_id,
        storage_path=video_object,
        ass_storage_path=ass_object,
        size_bytes=size_bytes,
        duration_ms=duration_ms,
        width=width,
        height=height,
    )
    jobs.mark_succeeded(
        owner_uid=owner_uid,
        project_id=project_id,
        job_id=job_id,
        output={
            "artifactIds": [],
            "storagePaths": [video_object, ass_object],
            "captionRenderId": caption_render_id,
        },
        message="Captioned video ready",
    )
    logger.info(
        "caption render %s done: %dx%d, %.1fs, %.1f MB",
        caption_render_id,
        width,
        height,
        duration_ms / 1000,
        size_bytes / 1e6,
    )


def _style_from(render: dict[str, Any]) -> CaptionStyle:
    raw = render.get("style")
    if isinstance(raw, dict):
        try:
            return CaptionStyle.model_validate(raw)
        except Exception:  # noqa: BLE001 - fall back to the default look
            logger.warning("caption render has an invalid style; using defaults")
    return CaptionStyle()


def _failure_message(exc: BaseException) -> str:
    if isinstance(exc, VideoToolError):
        detail = str(exc).strip()
        if detail:
            return f"Caption render failed: {detail}"
    return "Caption render failed. Try again."


# --------------------------------------------------------------------------- wiring


def build_worker_services(
    *,
    firestore: FirestoreClient,
    jobs: JobService,
    projects: ProjectService,
    captions: CaptionRenderService,
    transcripts: TranscriptService,
    storage: StorageClient,
    settings: Settings,
) -> dict[str, Any]:
    return {
        "firestore": firestore,
        "jobs": jobs,
        "projects": projects,
        "captions": captions,
        "transcripts": transcripts,
        "storage": storage,
        "settings": settings,
    }


def live_worker_dependencies() -> dict[str, Any]:
    firestore = get_firestore_client()
    settings = get_settings()
    storage = get_storage_client()
    jobs = JobService(firestore)
    projects = ProjectService(firestore, storage=storage)
    transcripts = TranscriptService(firestore, storage=storage)
    return build_worker_services(
        firestore=firestore,
        jobs=jobs,
        projects=projects,
        captions=CaptionRenderService(
            firestore,
            projects=projects,
            jobs=jobs,
            transcripts=transcripts,
            storage=storage,
            url_ttl_seconds=settings.upload_url_ttl_seconds,
        ),
        transcripts=transcripts,
        storage=storage,
        settings=settings,
    )


def caption_render_after_response(
    background_tasks: Any,
    *,
    owner_uid: str,
    project_id: str,
    job_id: str,
) -> None:
    """Run the caption render worker after the HTTP response is sent."""
    background_tasks.add_task(
        run_caption_render,
        owner_uid=owner_uid,
        project_id=project_id,
        job_id=job_id,
        **live_worker_dependencies(),
    )
