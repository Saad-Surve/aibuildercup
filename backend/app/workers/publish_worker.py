"""Publish worker: push a project's video, thumbnail, and captions to a connected channel.

Pipeline for a `publish` job:

1. Load the publish record and the connection's (refreshed) tokens.
2. Stage the chosen video locally (bounded by `PUBLISH_MAX_SOURCE_BYTES`).
3. Upload it to YouTube with the resumable protocol, reporting byte progress to the job.
4. Set the custom thumbnail and upload the caption track.
5. Mark the publish `published` and record the YouTube video id/url.

The worker is idempotent: a terminal publish is skipped, so a redelivered job cannot upload the
same video twice.
"""

import asyncio
import logging
import os
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.config import Settings
from app.connectors.base import ConnectorError
from app.connectors.youtube import YouTubeConnector
from app.errors import NotFoundError
from app.schemas.jobs import JobStatus
from app.schemas.publishes import (
    PublishCaptionFormat,
    PublishStatus,
    PublishWarning,
    PublishWarningCode,
)
from app.services.connection_service import ConnectionService
from app.services.firestore_service import FirestoreClient
from app.services.job_service import JobService
from app.services.publish_service import PublishService
from app.services.storage_service import StorageClient
from app.services.token_cipher import build_token_cipher
from app.workers.guard import serialize_job

logger = logging.getLogger(__name__)

_VERIFY_URL = "https://www.youtube.com/verify"

TERMINAL_STATUSES = frozenset(
    {JobStatus.succeeded.value, JobStatus.failed.value, JobStatus.cancelled.value}
)

#: Where the upload sits inside the job's overall percent, so the UI moves through the
#: encoding-independent part of the pipeline.
_UPLOAD_PERCENT_START = 10
_UPLOAD_PERCENT_END = 85


def _stage_storage_object(
    storage: StorageClient,
    *,
    storage_path: str,
    suffix: str,
    max_bytes: int,
) -> Path:
    """Download one Cloud Storage object to a temp file, refusing oversized objects."""
    size = storage.object_size(storage_path)
    if size is not None and size > max_bytes:
        raise ConnectorError(
            "This video is larger than the publish limit.",
            code="PUBLISH_SOURCE_TOO_LARGE",
            details={"sizeBytes": size, "maxBytes": max_bytes},
        )
    handle = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    handle.close()
    local = Path(handle.name)
    storage.download_to_filename(storage_path, str(local))
    return local


def _cleanup(path: Path | None) -> None:
    if path is None:
        return
    try:
        os.unlink(path)
    except OSError:
        pass


def _suffix_for(mime_type: str) -> str:
    mapping = {
        "video/mp4": ".mp4",
        "video/quicktime": ".mov",
        "video/webm": ".webm",
        "video/x-m4v": ".m4v",
        "image/png": ".png",
        "image/jpeg": ".jpg",
        "image/webp": ".webp",
    }
    return mapping.get(mime_type, ".bin")


@serialize_job
async def run_publish(
    *,
    owner_uid: str,
    project_id: str,
    job_id: str,
    firestore: FirestoreClient,
    jobs: JobService,
    publishes: PublishService,
    connections: ConnectionService,
    connector: YouTubeConnector,
    storage: StorageClient,
    settings: Settings,
) -> str | None:
    try:
        job = await asyncio.to_thread(
            jobs.load_for_worker, owner_uid=owner_uid, project_id=project_id, job_id=job_id
        )
    except NotFoundError:
        logger.warning("publish job %s not found; skipping", job_id)
        return None
    if job.get("status") in TERMINAL_STATUSES:
        logger.info("publish job %s already %s; skipping", job_id, job.get("status"))
        return (job.get("input") or {}).get("publishId")

    publish_id = (job.get("input") or {}).get("publishId")
    if not publish_id:
        await asyncio.to_thread(
            jobs.mark_failed,
            owner_uid=owner_uid,
            project_id=project_id,
            job_id=job_id,
            message="This upload could not start. Start a new upload.",
            code="PUBLISH_FAILED",
        )
        return None

    try:
        publish = await asyncio.to_thread(
            publishes.load, owner_uid=owner_uid, project_id=project_id, publish_id=publish_id
        )
    except NotFoundError:
        await asyncio.to_thread(
            jobs.mark_failed,
            owner_uid=owner_uid,
            project_id=project_id,
            job_id=job_id,
            message="This upload was deleted. Start a new one.",
            code="PUBLISH_FAILED",
        )
        return publish_id

    if publish.get("status") == PublishStatus.published.value:
        await asyncio.to_thread(
            jobs.mark_succeeded,
            owner_uid=owner_uid,
            project_id=project_id,
            job_id=job_id,
            output={"publishIds": [publish_id]},
            message="Already published",
        )
        return publish_id

    await asyncio.to_thread(
        jobs.mark_running,
        owner_uid=owner_uid,
        project_id=project_id,
        job_id=job_id,
        step="publishing",
        message="Preparing the upload",
    )
    await asyncio.to_thread(
        publishes.mark_status,
        owner_uid=owner_uid,
        project_id=project_id,
        publish_id=publish_id,
        status=PublishStatus.uploading,
        step="Preparing the upload",
    )

    video_path: Path | None = None
    thumbnail_path: Path | None = None
    try:
        tokens = await asyncio.to_thread(
            connections.tokens_for_use,
            owner_uid=owner_uid,
            connection_id=str(publish["connectionId"]),
        )

        video_path = await asyncio.to_thread(
            _stage_storage_object,
            storage,
            storage_path=str(publish["videoStoragePath"]),
            suffix=_suffix_for(str(publish.get("videoMimeType") or "video/mp4")),
            # The business limit and the runtime temp-disk limit both apply; the smaller wins.
            max_bytes=min(settings.publish_max_source_bytes, settings.publish_max_stage_bytes),
        )

        def on_progress(fraction: int) -> None:
            span = _UPLOAD_PERCENT_END - _UPLOAD_PERCENT_START
            clamped = max(0, min(100, fraction))
            percent = _UPLOAD_PERCENT_START + int(round(span * clamped / 100))
            _report_progress(
                jobs,
                publishes,
                owner_uid=owner_uid,
                project_id=project_id,
                job_id=job_id,
                publish_id=publish_id,
                percent=percent,
                upload_progress=clamped,
                message="Uploading the video to YouTube",
            )

        await asyncio.to_thread(
            publishes.mark_status,
            owner_uid=owner_uid,
            project_id=project_id,
            publish_id=publish_id,
            status=PublishStatus.uploading,
            step="Uploading the video to YouTube",
        )
        # A scheduled go-public time drives both the upload status and privacy:
        # in the future YouTube holds the video private until then; if the moment
        # already passed, upload it public now (the go-live was intended).
        scheduled_at = _iso_or_none(publish.get("publishAt"))
        goes_live_later = False
        upload_publish_at: str | None = None
        upload_privacy = str(publish.get("privacyStatus") or "private")
        if scheduled_at is not None:
            moment = datetime.fromisoformat(scheduled_at.replace("Z", "+00:00"))
            if moment > datetime.now(UTC):
                goes_live_later = True
                upload_publish_at = scheduled_at
                upload_privacy = "private"
            else:
                upload_privacy = "public"
        uploaded = await asyncio.to_thread(
            connector.upload_video,
            tokens,
            path=video_path,
            title=str(publish["title"]),
            description=str(publish.get("description") or ""),
            tags=list(publish.get("tags") or []),
            category_id=str(publish.get("categoryId") or "22"),
            privacy_status=upload_privacy,
            made_for_kids=bool(publish.get("madeForKids", False)),
            notify_subscribers=bool(publish.get("notifySubscribers", True)),
            publish_at=upload_publish_at,
            on_progress=on_progress,
            mime_type=str(publish.get("videoMimeType") or "video/mp4"),
        )
        youtube_url = f"https://www.youtube.com/watch?v={uploaded.video_id}"
        await asyncio.to_thread(
            publishes.mark_status,
            owner_uid=owner_uid,
            project_id=project_id,
            publish_id=publish_id,
            status=PublishStatus.processing,
            step="Uploaded; YouTube is processing",
            upload_progress=100,
            youtube_video_id=uploaded.video_id,
            youtube_url=youtube_url,
        )

        # Thumbnail: optional, and best-effort — a channel without verified custom-thumbnail
        # access will reject it, which must not fail a video that is already uploaded.
        if not publish.get("thumbnailStoragePath"):
            await asyncio.to_thread(
                publishes.add_warning,
                owner_uid=owner_uid,
                project_id=project_id,
                publish_id=publish_id,
                warning=PublishWarning(
                    code=PublishWarningCode.THUMBNAIL_MISSING,
                    message=(
                        "No thumbnail was selected, so YouTube chose an automatic frame. "
                        "You can set a custom thumbnail on YouTube."
                    ),
                    step="thumbnail",
                ),
            )
        else:
            try:
                await asyncio.to_thread(
                    _report_progress,
                    jobs,
                    publishes,
                    owner_uid=owner_uid,
                    project_id=project_id,
                    job_id=job_id,
                    publish_id=publish_id,
                    percent=90,
                    message="Setting the thumbnail",
                )
                thumbnail_path = await asyncio.to_thread(
                    _stage_storage_object,
                    storage,
                    storage_path=str(publish["thumbnailStoragePath"]),
                    suffix=_suffix_for(str(publish.get("thumbnailMimeType") or "image/png")),
                    max_bytes=50 * 1024 * 1024,
                )
                await asyncio.to_thread(
                    connector.set_thumbnail,
                    tokens,
                    video_id=uploaded.video_id,
                    path=thumbnail_path,
                    mime_type=str(publish.get("thumbnailMimeType") or "image/png"),
                )
                await asyncio.to_thread(
                    publishes.mark_status,
                    owner_uid=owner_uid,
                    project_id=project_id,
                    publish_id=publish_id,
                    status=PublishStatus.processing,
                    step="Thumbnail set",
                )
            except ConnectorError as exc:
                logger.warning(
                    "publish %s: thumbnail rejected (%s): %s",
                    publish_id,
                    exc.code,
                    exc.message,
                )
                forbidden = exc.code == "YOUTUBE_FORBIDDEN"
                await asyncio.to_thread(
                    publishes.add_warning,
                    owner_uid=owner_uid,
                    project_id=project_id,
                    publish_id=publish_id,
                    warning=PublishWarning(
                        code=(
                            PublishWarningCode.THUMBNAIL_FORBIDDEN
                            if forbidden
                            else PublishWarningCode.THUMBNAIL_FAILED
                        ),
                        message=(
                            "YouTube did not accept the custom thumbnail because this channel "
                            "is not allowed to set one. Verify the channel by phone at "
                            f"{_VERIFY_URL} (YouTube settings), then set the thumbnail on the "
                            "video afterwards."
                            if forbidden
                            else f"The thumbnail could not be set ({exc.message}). "
                            "You can set it on the video in YouTube."
                        ),
                        step="thumbnail",
                    ),
                )
                await asyncio.to_thread(
                    publishes.mark_status,
                    owner_uid=owner_uid,
                    project_id=project_id,
                    publish_id=publish_id,
                    status=PublishStatus.processing,
                    step="Thumbnail skipped",
                )

        if publish.get("captionFormat") != PublishCaptionFormat.none.value:
            if not str(publish.get("captionContent") or "").strip():
                await asyncio.to_thread(
                    publishes.add_warning,
                    owner_uid=owner_uid,
                    project_id=project_id,
                    publish_id=publish_id,
                    warning=PublishWarning(
                        code=PublishWarningCode.CAPTIONS_SKIPPED,
                        message="No caption text was available, so no caption track was uploaded.",
                        step="captions",
                    ),
                )
            else:
                await asyncio.to_thread(
                    _report_progress,
                    jobs,
                    publishes,
                    owner_uid=owner_uid,
                    project_id=project_id,
                    job_id=job_id,
                    publish_id=publish_id,
                    percent=95,
                    message="Uploading the caption track",
                )
                try:
                    await asyncio.to_thread(
                        connector.upload_caption,
                        tokens,
                        video_id=uploaded.video_id,
                        content=str(publish["captionContent"]),
                        language=str(publish.get("captionLanguage") or "en"),
                        name=str(publish.get("captionName") or "English"),
                    )
                except ConnectorError as exc:
                    # The video is already on YouTube; a caption failure must not fail it.
                    logger.warning(
                        "publish %s: captions rejected (%s): %s",
                        publish_id,
                        exc.code,
                        exc.message,
                    )
                    await asyncio.to_thread(
                        publishes.add_warning,
                        owner_uid=owner_uid,
                        project_id=project_id,
                        publish_id=publish_id,
                        warning=PublishWarning(
                            code=PublishWarningCode.CAPTIONS_FAILED,
                            message=(
                                f"The caption track could not be uploaded ({exc.message}). "
                                "You can add captions to the video in YouTube Studio."
                            ),
                            step="captions",
                        ),
                    )
                else:
                    await asyncio.to_thread(
                        publishes.mark_status,
                        owner_uid=owner_uid,
                        project_id=project_id,
                        publish_id=publish_id,
                        status=PublishStatus.processing,
                        step="Captions uploaded",
                    )

        # A future go-public time means the upload is done but YouTube holds the
        # video private until then. Keep the publish `processing` (not
        # `published`) so the calendar slot and the "is live" notification wait
        # for the real moment; `PublishService.list/get` promotes it once due.
        await asyncio.to_thread(
            publishes.mark_status,
            owner_uid=owner_uid,
            project_id=project_id,
            publish_id=publish_id,
            status=(
                PublishStatus.processing if goes_live_later else PublishStatus.published
            ),
            step=(
                f"Scheduled to go public {scheduled_at}"
                if goes_live_later
                else "Published"
            ),
            upload_progress=100,
            youtube_video_id=uploaded.video_id,
            youtube_url=youtube_url,
        )
        await asyncio.to_thread(
            jobs.mark_succeeded,
            owner_uid=owner_uid,
            project_id=project_id,
            job_id=job_id,
            output={"publishIds": [publish_id], "youtubeVideoId": uploaded.video_id},
            message=(
                "Uploaded; scheduled on YouTube"
                if goes_live_later
                else "Published to YouTube"
            ),
        )
        return publish_id
    except ConnectorError as exc:
        _fail(
            jobs,
            publishes,
            owner_uid=owner_uid,
            project_id=project_id,
            job_id=job_id,
            publish_id=publish_id,
            code=exc.code,
            message=exc.message,
        )
        return publish_id
    except Exception as exc:  # noqa: BLE001 - normalised into a failed publish
        logger.exception(f"publish %s failed: {exc}", publish_id)
        _fail(
            jobs,
            publishes,
            owner_uid=owner_uid,
            project_id=project_id,
            job_id=job_id,
            publish_id=publish_id,
            code="PUBLISH_FAILED",
            message="Publishing failed. Check your connected account and try again.",
        )
        return publish_id
    finally:
        _cleanup(video_path)
        _cleanup(thumbnail_path)


def _report_progress(
    jobs: JobService,
    publishes: PublishService,
    *,
    owner_uid: str,
    project_id: str,
    job_id: str,
    publish_id: str,
    percent: int,
    message: str,
    upload_progress: int | None = None,
) -> None:
    try:
        jobs.update_progress(
            owner_uid=owner_uid,
            project_id=project_id,
            job_id=job_id,
            percent=percent,
            step="publishing",
            message=message,
        )
        publishes.mark_status(
            owner_uid=owner_uid,
            project_id=project_id,
            publish_id=publish_id,
            status=PublishStatus.uploading,
            upload_progress=upload_progress if upload_progress is not None else percent,
        )
    except Exception:  # noqa: BLE001 - progress must never fail the upload
        logger.debug("publish: progress update failed", exc_info=True)


def _fail(
    jobs: JobService,
    publishes: PublishService,
    *,
    owner_uid: str,
    project_id: str,
    job_id: str,
    publish_id: str,
    code: str,
    message: str,
) -> None:
    jobs.mark_failed(
        owner_uid=owner_uid,
        project_id=project_id,
        job_id=job_id,
        message=message,
        code=code,
    )
    publishes.mark_status(
        owner_uid=owner_uid,
        project_id=project_id,
        publish_id=publish_id,
        status=PublishStatus.failed,
        step="Failed",
        error={"code": code, "message": message},
    )


def _iso_or_none(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        moment = value if value.tzinfo else value.replace(tzinfo=UTC)
        return moment.astimezone(UTC).isoformat().replace("+00:00", "Z")
    return str(value)


def build_worker_services(
    *,
    firestore: FirestoreClient,
    jobs: JobService,
    publishes: PublishService,
    connections: ConnectionService,
    connector: YouTubeConnector,
    storage: StorageClient,
    settings: Settings,
) -> dict[str, Any]:
    return {
        "firestore": firestore,
        "jobs": jobs,
        "publishes": publishes,
        "connections": connections,
        "connector": connector,
        "storage": storage,
        "settings": settings,
    }


def live_worker_dependencies() -> dict[str, Any]:
    from app.config import get_settings
    from app.connectors.youtube import YouTubeConnector as _YouTubeConnector
    from app.services.asset_service import AssetService
    from app.services.caption_service import CaptionRenderService
    from app.services.firestore_service import get_firestore_client
    from app.services.glossary_service import GlossaryService
    from app.services.localization_service import LocalizationService
    from app.services.project_service import ProjectService
    from app.services.storage_service import get_storage_client
    from app.services.thumbnail_service import ThumbnailService
    from app.services.transcript_service import TranscriptService

    settings = get_settings()
    firestore = get_firestore_client()
    storage = get_storage_client()
    jobs = JobService(firestore)
    projects = ProjectService(firestore, storage=storage)
    transcripts = TranscriptService(firestore, storage=storage)
    assets = AssetService(
        firestore,
        projects=projects,
        jobs=jobs,
        storage=storage,
        settings=settings,
    )
    captions = CaptionRenderService(
        firestore,
        projects=projects,
        jobs=jobs,
        transcripts=transcripts,
        storage=storage,
        url_ttl_seconds=settings.upload_url_ttl_seconds,
    )
    localizations = LocalizationService(
        firestore,
        projects=projects,
        jobs=jobs,
        transcripts=transcripts,
        glossaries=GlossaryService(firestore, projects=projects),
        storage=storage,
        url_ttl_seconds=settings.upload_url_ttl_seconds,
    )
    thumbnails = ThumbnailService(
        firestore,
        projects=projects,
        jobs=jobs,
        storage=storage,
        url_ttl_seconds=settings.upload_url_ttl_seconds,
        price_per_image_usd=settings.imagegen_price_per_image_usd,
        max_project_cost_usd=settings.max_project_cost_usd,
    )
    connections = ConnectionService(
        firestore, cipher=build_token_cipher(settings), settings=settings
    )
    publishes = PublishService(
        firestore,
        projects=projects,
        jobs=jobs,
        connections=connections,
        assets=assets,
        captions=captions,
        localizations=localizations,
        transcripts=transcripts,
        thumbnails=thumbnails,
        storage=storage,
        settings=settings,
    )
    connector = _YouTubeConnector(
        client_id=settings.google_oauth_client_id or "",
        client_secret=settings.google_oauth_client_secret or "",
    )
    return build_worker_services(
        firestore=firestore,
        jobs=jobs,
        publishes=publishes,
        connections=connections,
        connector=connector,
        storage=storage,
        settings=settings,
    )


def publish_after_response(
    background_tasks: Any,
    *,
    owner_uid: str,
    project_id: str,
    job_id: str,
) -> None:
    """Run the publish worker after the HTTP response is sent."""
    background_tasks.add_task(
        run_publish,
        owner_uid=owner_uid,
        project_id=project_id,
        job_id=job_id,
        **live_worker_dependencies(),
    )


__all__ = ["run_publish", "publish_after_response", "build_worker_services"]
