"""Publishing service: validate a publish request, pick the media, and queue the upload.

The service resolves the creator's chosen video, thumbnail, and captions to concrete Cloud
Storage objects (or an in-memory SRT built from the transcript) and records a `Publish` under the
project. The actual YouTube calls happen in `app/workers/publish_worker.py`.

Everything the worker needs (source kind + id, thumbnail id + version, caption format/language)
is frozen into the publish document at create time, so a later edit to a thumbnail concept or a
re-rendered dub cannot change an in-flight publish.
"""

import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from app.config import Settings
from app.errors import BadRequestError, ConflictError, NotFoundError
from app.schemas.assets import AssetType
from app.schemas.captions import CaptionRenderStatus
from app.schemas.connections import ConnectionStatus
from app.schemas.jobs import Job, JobType
from app.schemas.localizations import LocalizationStatus
from app.schemas.publishes import (
    Publish,
    PublishAccepted,
    PublishCaptionFormat,
    PublishRequest,
    PublishSourceKind,
    PublishStatus,
    PublishThumbnail,
    PublishVideoSource,
    PublishVisibility,
)
from app.schemas.thumbnails import ThumbnailStatus
from app.services.asset_service import AssetService
from app.services.caption_service import CaptionRenderService
from app.services.connection_service import ConnectionService
from app.services.firestore_service import (
    FirestoreClient,
    publish_path,
    publishes_collection_path,
)
from app.services.job_service import JobService
from app.services.localization_service import LocalizationService
from app.services.project_service import ProjectService
from app.services.storage_service import StorageClient
from app.services.thumbnail_service import ThumbnailService
from app.services.transcript_service import TranscriptService

logger = logging.getLogger(__name__)

#: How long a live video's existence is trusted before re-checking YouTube.
_RECONCILE_SECONDS = 60

#: (publishId, publish, raw document) — carried through the live-video reconcile.
#: A module-level alias, because inside `PublishService` the method named `list`
#: shadows the builtin `list` for every annotation below it.
_LiveItems = list[tuple[str, Publish, dict[str, Any]]]


@dataclass(frozen=True)
class ResolvedVideo:
    storage_path: str
    mime_type: str
    size_bytes: int
    duration_ms: int
    kind: PublishSourceKind
    reference_id: str | None


@dataclass(frozen=True)
class ResolvedThumbnail:
    thumbnail_id: str
    version: int
    storage_path: str
    mime_type: str
    size_bytes: int


@dataclass(frozen=True)
class ResolvedCaptions:
    content: str
    language: str
    name: str
    format: PublishCaptionFormat


def _to_publish(publish_id: str, data: dict[str, Any]) -> Publish:
    return Publish(
        publishId=publish_id,
        projectId=data.get("projectId", ""),
        connectionId=data.get("connectionId", ""),
        connectionDisplayName=data.get("connectionDisplayName"),
        platform=data.get("platform", "youtube"),
        status=PublishStatus(data.get("status", PublishStatus.queued.value)),
        video=PublishVideoSource(
            kind=PublishSourceKind(data.get("videoKind", "source")),
            id=data.get("videoId"),
        ),
        title=data.get("title", ""),
        description=data.get("description", ""),
        tags=list(data.get("tags") or []),
        categoryId=data.get("categoryId", "22"),
        privacyStatus=data.get("privacyStatus", "private"),
        madeForKids=bool(data.get("madeForKids", False)),
        notifySubscribers=bool(data.get("notifySubscribers", True)),
        captionFormat=PublishCaptionFormat(data.get("captionFormat", "srt")),
        captionLanguage=data.get("captionLanguage", "en"),
        captionName=data.get("captionName", "English"),
        thumbnailId=data.get("thumbnailId"),
        thumbnailVersion=data.get("thumbnailVersion"),
        youtubeVideoId=data.get("youtubeVideoId"),
        youtubeUrl=data.get("youtubeUrl"),
        uploadProgress=int(data.get("uploadProgress", 0) or 0),
        steps=list(data.get("steps") or []),
        jobId=data.get("jobId"),
        publishAt=data.get("publishAt"),
        error=data.get("error"),
        createdAt=data["createdAt"],
        updatedAt=data["updatedAt"],
    )


class PublishService:
    def __init__(
        self,
        client: FirestoreClient,
        *,
        projects: ProjectService,
        jobs: JobService,
        connections: ConnectionService,
        assets: AssetService,
        captions: CaptionRenderService,
        localizations: LocalizationService,
        transcripts: TranscriptService,
        thumbnails: ThumbnailService,
        storage: StorageClient,
        settings: Settings,
    ) -> None:
        self.client = client
        self.projects = projects
        self.jobs = jobs
        self.connections = connections
        self.assets = assets
        self.captions = captions
        self.localizations = localizations
        self.transcripts = transcripts
        self.thumbnails = thumbnails
        self.storage = storage
        self.settings = settings

    # ------------------------------------------------------------------ create

    def create(
        self, *, owner_uid: str, project_id: str, payload: PublishRequest
    ) -> tuple[Publish, Job]:
        project = self.projects.get(owner_uid=owner_uid, project_id=project_id)
        connection = self.connections.get(
            owner_uid=owner_uid, connection_id=payload.connectionId
        )
        if connection.status != ConnectionStatus.connected:
            raise BadRequestError(
                "Reconnect this channel before publishing.",
                code="CONNECTION_NEEDS_REAUTH",
                details={"connectionId": payload.connectionId, "status": connection.status},
            )

        video = self._resolve_video(owner_uid, project_id, payload.video, project.sourceAssetId)
        if video.size_bytes > self.settings.publish_max_source_bytes:
            raise BadRequestError(
                "This video is larger than the publish limit.",
                code="PUBLISH_SOURCE_TOO_LARGE",
                details={
                    "sizeBytes": video.size_bytes,
                    "maxBytes": self.settings.publish_max_source_bytes,
                },
            )
        thumbnail = self._resolve_thumbnail(owner_uid, project_id, payload)
        captions = self._resolve_captions(owner_uid, project_id, payload, video)

        publish_id = uuid4().hex
        now = datetime.now(UTC)
        document: dict[str, Any] = {
            "ownerUid": owner_uid,
            "projectId": project_id,
            "connectionId": payload.connectionId,
            "connectionDisplayName": connection.displayName,
            "platform": "youtube",
            "status": PublishStatus.queued.value,
            "videoKind": video.kind.value,
            "videoId": video.reference_id,
            "videoStoragePath": video.storage_path,
            "videoMimeType": video.mime_type,
            "videoSizeBytes": video.size_bytes,
            "title": payload.title,
            "description": payload.description,
            "tags": payload.tags,
            "categoryId": payload.categoryId,
            "privacyStatus": payload.privacyStatus.value,
            "madeForKids": payload.madeForKids,
            "notifySubscribers": payload.notifySubscribers,
            "publishAt": payload.publishAt,
            "captionFormat": captions.format.value,
            "captionLanguage": captions.language,
            "captionName": captions.name,
            #: The resolved caption text is kept so the worker does not re-read the transcript
            #: mid-upload and a running publish is reproducible.
            "captionContent": captions.content,
            "thumbnailId": thumbnail.thumbnail_id if thumbnail else None,
            "thumbnailVersion": thumbnail.version if thumbnail else None,
            "thumbnailStoragePath": thumbnail.storage_path if thumbnail else None,
            "thumbnailMimeType": thumbnail.mime_type if thumbnail else None,
            "youtubeVideoId": None,
            "youtubeUrl": None,
            "uploadProgress": 0,
            "steps": ["Queued"],
            "jobId": None,
            "error": None,
            "createdAt": now,
            "updatedAt": now,
        }
        self.client.set_document(publish_path(owner_uid, project_id, publish_id), document)

        job = self.jobs.create(
            owner_uid=owner_uid,
            project_id=project_id,
            job_type=JobType.publish,
            idempotency_key=f"publish-{project_id}-{publish_id}",
            input={"publishId": publish_id},
        )
        self.client.update_document(
            publish_path(owner_uid, project_id, publish_id), {"jobId": job.jobId}
        )
        document["jobId"] = job.jobId
        return _to_publish(publish_id, document), job

    def _resolve_video(
        self,
        owner_uid: str,
        project_id: str,
        source: PublishVideoSource,
        active_source_id: str | None,
    ) -> ResolvedVideo:
        if source.kind == PublishSourceKind.source:
            if not source.id and not active_source_id:
                raise NotFoundError(
                    "This project has no source video.", details={"projectId": project_id}
                )
            asset = self.assets.get_asset(
                owner_uid=owner_uid,
                project_id=project_id,
                asset_id=source.id or str(active_source_id),
            )
            if asset.type != AssetType.source_video.value:
                raise NotFoundError("Source video not found", details={"assetId": asset.assetId})
            return ResolvedVideo(
                storage_path=asset.storagePath,
                mime_type=asset.mimeType or "video/mp4",
                size_bytes=asset.sizeBytes,
                duration_ms=asset.durationMs or 0,
                kind=source.kind,
                reference_id=asset.assetId,
            )

        if source.kind == PublishSourceKind.captionRender:
            if not source.id:
                raise BadRequestError(
                    "A caption render id is required.", code="PUBLISH_VIDEO_REQUIRED"
                )
            render = self.captions.get(
                owner_uid=owner_uid, project_id=project_id, caption_render_id=source.id
            )
            if render.status != CaptionRenderStatus.ready or not render.storagePath:
                raise BadRequestError(
                    "That caption render is not ready yet.",
                    code="PUBLISH_VIDEO_NOT_READY",
                    details={"captionRenderId": source.id, "status": render.status},
                )
            return ResolvedVideo(
                storage_path=render.storagePath,
                mime_type=render.mimeType or "video/mp4",
                size_bytes=render.sizeBytes,
                duration_ms=render.durationMs,
                kind=source.kind,
                reference_id=render.captionRenderId,
            )

        if not source.id:
            raise BadRequestError(
                "A localization id is required.", code="PUBLISH_VIDEO_REQUIRED"
            )
        localization = self.localizations.get(
            owner_uid=owner_uid, project_id=project_id, localization_id=source.id
        )
        if localization.status != LocalizationStatus.ready or not localization.videoStoragePath:
            raise BadRequestError(
                "That dub is not ready yet.",
                code="PUBLISH_VIDEO_NOT_READY",
                details={"localizationId": source.id, "status": localization.status},
            )
        return ResolvedVideo(
            storage_path=localization.videoStoragePath,
            mime_type=localization.mimeType or "video/mp4",
            size_bytes=localization.sizeBytes,
            duration_ms=localization.durationMs,
            kind=source.kind,
            reference_id=localization.localizationId,
        )

    def _resolve_thumbnail(
        self, owner_uid: str, project_id: str, payload: PublishRequest
    ) -> ResolvedThumbnail | None:
        if payload.thumbnail is None:
            return None
        concept = self.thumbnails.get(
            owner_uid=owner_uid,
            project_id=project_id,
            thumbnail_id=payload.thumbnail.thumbnailId,
        )
        if concept.status != ThumbnailStatus.ready:
            raise BadRequestError(
                "That thumbnail is not ready yet.",
                code="PUBLISH_THUMBNAIL_NOT_READY",
                details={"thumbnailId": payload.thumbnail.thumbnailId, "status": concept.status},
            )
        versions = [version for version in concept.versions if version.storagePath]
        if not versions:
            raise BadRequestError(
                "That thumbnail has no generated image yet.",
                code="PUBLISH_THUMBNAIL_NOT_READY",
            )
        chosen = None
        if payload.thumbnail.version is not None:
            chosen = next(
                (version for version in versions if version.version == payload.thumbnail.version),
                None,
            )
            if chosen is None:
                raise NotFoundError(
                    "Thumbnail version not found",
                    details={
                        "thumbnailId": payload.thumbnail.thumbnailId,
                        "version": payload.thumbnail.version,
                    },
                )
        else:
            chosen = max(versions, key=lambda version: version.version)
        assert chosen is not None and chosen.storagePath is not None
        return ResolvedThumbnail(
            thumbnail_id=payload.thumbnail.thumbnailId,
            version=chosen.version,
            storage_path=chosen.storagePath,
            mime_type=chosen.mimeType or "image/png",
            size_bytes=chosen.sizeBytes,
        )

    def _resolve_captions(
        self,
        owner_uid: str,
        project_id: str,
        payload: PublishRequest,
        video: ResolvedVideo,
    ) -> ResolvedCaptions:
        if payload.captionFormat == PublishCaptionFormat.none:
            return ResolvedCaptions(
                content="",
                language=payload.captionLanguage,
                name=payload.captionName,
                format=PublishCaptionFormat.none,
            )

        # A localized dub ships its own translated SRT; prefer it when present.
        if video.kind == PublishSourceKind.localization and video.reference_id:
            localization = self.localizations.get(
                owner_uid=owner_uid, project_id=project_id, localization_id=video.reference_id
            )
            if (
                localization.captionsStoragePath
                and payload.captionFormat == PublishCaptionFormat.srt
            ):
                try:
                    content = self.storage.download_text(localization.captionsStoragePath)
                except Exception:  # noqa: BLE001 - fall back to the transcript
                    logger.warning("publish: localized captions missing; using transcript")
                else:
                    return ResolvedCaptions(
                        content=content,
                        language=localization.targetLanguage or payload.captionLanguage,
                        name=payload.captionName,
                        format=PublishCaptionFormat.srt,
                    )

        from app.services.transcript_service import build_srt, build_vtt

        transcript = self.transcripts.get(owner_uid=owner_uid, project_id=project_id)
        segments = [segment.model_dump() for segment in transcript.segments]
        if payload.captionFormat == PublishCaptionFormat.vtt:
            content = build_vtt(segments)
        else:
            content = build_srt(segments)
        return ResolvedCaptions(
            content=content,
            language=payload.captionLanguage or transcript.language,
            name=payload.captionName,
            format=payload.captionFormat,
        )

    # ------------------------------------------------------------------ read

    def list(self, *, owner_uid: str, project_id: str) -> list[Publish]:
        self.projects.get(owner_uid=owner_uid, project_id=project_id)
        rows = self.client.query_collection(
            publishes_collection_path(owner_uid, project_id),
            filters=[],
            order_by=[("createdAt", "DESCENDING")],
            limit=50,
            offset=0,
        )
        items = [
            (
                publish_id,
                self._promote_due(owner_uid, project_id, _to_publish(publish_id, data)),
                data,
            )
            for publish_id, data in rows
            if data.get("ownerUid") == owner_uid
        ]
        items = self._reconcile_live(owner_uid, project_id, items)
        return [publish for _, publish, _ in items]

    def get(self, *, owner_uid: str, project_id: str, publish_id: str) -> Publish:
        data = self._require(owner_uid, project_id, publish_id)
        publish = self._promote_due(
            owner_uid, project_id, _to_publish(publish_id, data)
        )
        items = self._reconcile_live(owner_uid, project_id, [(publish_id, publish, data)])
        return items[0][1]

    def _reconcile_live(
        self,
        owner_uid: str,
        project_id: str,
        items: _LiveItems,
    ) -> _LiveItems:
        """Notice a live video that was deleted directly on YouTube.

        Batched, throttled `videos.list` per connection; an id the API no longer
        returns marks the publish `deleted` and cancels its linked calendar slot.
        A failed check leaves every publish untouched.
        """
        now = datetime.now(UTC)
        stale = [
            (publish_id, publish)
            for publish_id, publish, data in items
            if publish.status == PublishStatus.published
            and publish.youtubeVideoId
            and self._check_due(data.get("videoCheckedAt"), now)
        ]
        if not stale:
            return items

        by_connection: dict[str, list[Publish]] = {}
        for _, publish in stale:
            by_connection.setdefault(publish.connectionId, []).append(publish)

        checked: set[str] = set()
        existing: set[str] = set()
        for connection_id, group in by_connection.items():
            ids = [p.youtubeVideoId for p in group if p.youtubeVideoId]
            try:
                tokens = self.connections.tokens_for_use(
                    owner_uid=owner_uid, connection_id=connection_id
                )
                existing |= self._youtube_connector().existing_video_ids(
                    tokens, video_ids=ids
                )
            except Exception:  # noqa: BLE001 - a check failure must not break a read
                logger.warning(
                    "publish reconcile: could not check %d video(s) on connection %s",
                    len(ids),
                    connection_id,
                    exc_info=True,
                )
                continue
            checked.update(ids)

        updates: dict[str, Publish] = {}
        for publish_id, publish in stale:
            video_id = publish.youtubeVideoId
            if video_id is None or video_id not in checked:
                continue
            if video_id in existing:
                self.client.update_document(
                    publish_path(owner_uid, project_id, publish_id),
                    {"videoCheckedAt": now},
                )
                continue
            self._mark_deleted(owner_uid, project_id, publish_id)
            updates[publish_id] = _to_publish(
                publish_id, self._require(owner_uid, project_id, publish_id)
            )

        if not updates:
            return items
        return [
            (publish_id, updates.get(publish_id, publish), data)
            for publish_id, publish, data in items
        ]

    @staticmethod
    def _check_due(checked: Any, now: datetime) -> bool:
        if not isinstance(checked, datetime):
            return True
        moment = checked if checked.tzinfo else checked.replace(tzinfo=UTC)
        return (now - moment.astimezone(UTC)).total_seconds() >= _RECONCILE_SECONDS

    def _youtube_connector(self) -> Any:
        from app.connectors.youtube import YouTubeConnector

        return YouTubeConnector(
            client_id=self.settings.google_oauth_client_id or "",
            client_secret=self.settings.google_oauth_client_secret or "",
        )

    def _mark_deleted(self, owner_uid: str, project_id: str, publish_id: str) -> None:
        self.mark_status(
            owner_uid=owner_uid,
            project_id=project_id,
            publish_id=publish_id,
            status=PublishStatus.deleted,
            step="Deleted on YouTube",
            error={
                "code": "YOUTUBE_VIDEO_DELETED",
                "message": "This video was deleted directly on YouTube.",
            },
        )

    def recreate_for_schedule(
        self,
        *,
        owner_uid: str,
        project_id: str,
        source: dict[str, Any],
        publish_at: datetime,
    ) -> tuple[Publish, Job]:
        """Queue a fresh upload for a calendar slot whose linked publish is dead.

        Copies the dead publish's settings (video source, title, channel,
        captions, thumbnail) so a rescheduled slot uploads the same thing again.
        """
        thumbnail = None
        if source.get("thumbnailId"):
            thumbnail = PublishThumbnail(
                thumbnailId=str(source["thumbnailId"]),
                version=source.get("thumbnailVersion"),
            )
        payload = PublishRequest(
            connectionId=str(source["connectionId"]),
            video=PublishVideoSource(
                kind=PublishSourceKind(source.get("videoKind") or "source"),
                id=source.get("videoId"),
            ),
            title=str(source.get("title") or "Untitled"),
            description=str(source.get("description") or ""),
            tags=list(source.get("tags") or []),
            categoryId=str(source.get("categoryId") or "22"),
            privacyStatus=PublishVisibility(source.get("privacyStatus") or "private"),
            madeForKids=bool(source.get("madeForKids", False)),
            notifySubscribers=bool(source.get("notifySubscribers", True)),
            captionFormat=PublishCaptionFormat(source.get("captionFormat") or "srt"),
            captionLanguage=str(source.get("captionLanguage") or "en"),
            captionName=str(source.get("captionName") or "English"),
            thumbnail=thumbnail,
            publishAt=publish_at,
        )
        return self.create(owner_uid=owner_uid, project_id=project_id, payload=payload)

    def reschedule_on_youtube(
        self, *, owner_uid: str, project_id: str, publish_id: str
    ) -> None:
        """Move a waiting (private, scheduled) video's go-public time on YouTube."""
        data = self._require(owner_uid, project_id, publish_id)
        video_id = data.get("youtubeVideoId")
        moment = data.get("publishAt")
        if not video_id or not isinstance(moment, datetime):
            return
        when = moment if moment.tzinfo else moment.replace(tzinfo=UTC)
        iso = when.astimezone(UTC).isoformat().replace("+00:00", "Z")
        tokens = self.connections.tokens_for_use(
            owner_uid=owner_uid, connection_id=str(data.get("connectionId"))
        )
        self._youtube_connector().update_publish_at(
            tokens, video_id=str(video_id), publish_at=iso
        )

    def _promote_due(
        self, owner_uid: str, project_id: str, publish: Publish
    ) -> Publish:
        """Flip a scheduled upload to `published` once its go-public time passes.

        YouTube holds the video private until `publishAt`, so until then the
        publish stays `processing` and its linked calendar slot stays
        `scheduled`. There is no scheduler in this runtime, so promotion happens
        lazily when a publish is read — the notification watcher polls `list`
        every cycle, so the "went live" notification and the calendar flip both
        fire then.
        """
        if (
            publish.status != PublishStatus.processing
            or publish.publishAt is None
            or publish.youtubeVideoId is None
        ):
            return publish
        moment = publish.publishAt
        if moment.tzinfo is None:
            moment = moment.replace(tzinfo=UTC)
        if moment.astimezone(UTC) > datetime.now(UTC):
            return publish
        self.mark_status(
            owner_uid=owner_uid,
            project_id=project_id,
            publish_id=publish.publishId,
            status=PublishStatus.published,
            step="Published",
            upload_progress=100,
        )
        return _to_publish(
            publish.publishId, self._require(owner_uid, project_id, publish.publishId)
        )

    def delete(self, *, owner_uid: str, project_id: str, publish_id: str) -> None:
        """Delete an upload attempt and detach its calendar slots.

        A still-queued job is cancelled first so nothing uploads after the record
        is gone (the worker treats a cancelled job as terminal and skips it).
        Linked slots go back to `planned`/`failed` with an explanation instead of
        pointing at a missing publish forever; already-uploaded videos stay on
        YouTube — deleting the attempt never deletes the video itself.
        """
        data = self._require(owner_uid, project_id, publish_id)
        job_id = data.get("jobId")
        if job_id and not data.get("youtubeVideoId"):
            try:
                self.jobs.cancel(owner_uid=owner_uid, job_id=str(job_id))
            except (ConflictError, NotFoundError):
                pass
            except Exception:  # noqa: BLE001 - the delete must still go through
                logger.warning(
                    "publish: could not cancel job %s for deleted publish %s",
                    job_id,
                    publish_id,
                )
        self.client.delete_document(publish_path(owner_uid, project_id, publish_id))
        from app.services.schedule_service import ScheduleService

        ScheduleService(self.client, projects=self.projects).unlink_publish(
            owner_uid=owner_uid, project_id=project_id, publish_id=publish_id
        )

    def retry(self, *, owner_uid: str, project_id: str, publish_id: str) -> tuple[Publish, Job]:
        """Re-queue a failed publish. Finished/queued publishes are a conflict."""
        data = self._require(owner_uid, project_id, publish_id)
        if data.get("status") != PublishStatus.failed.value:
            raise ConflictError(
                "Only a failed publish can be retried.",
                code="PUBLISH_NOT_RETRYABLE",
                details={"publishId": publish_id, "status": data.get("status")},
            )
        job_id = data.get("jobId")
        if not job_id:
            raise ConflictError(
                "This publish has no job to retry.",
                code="PUBLISH_NOT_RETRYABLE",
                details={"publishId": publish_id},
            )
        job = self.jobs.requeue_failed(
            owner_uid=owner_uid,
            project_id=project_id,
            job_id=job_id,
            input={"publishId": publish_id},
        )
        self.client.update_document(
            publish_path(owner_uid, project_id, publish_id),
            {
                "status": PublishStatus.queued.value,
                "error": None,
                "uploadProgress": 0,
                "steps": ["Queued"],
                "updatedAt": datetime.now(UTC),
            },
        )
        # The retry is queued: the calendar slot stops being a failure and waits again.
        from app.services.schedule_service import ScheduleService

        ScheduleService(self.client, projects=self.projects).mark_linked_scheduled(
            owner_uid=owner_uid, project_id=project_id, publish_id=publish_id
        )
        return self.get(owner_uid=owner_uid, project_id=project_id, publish_id=publish_id), job

    def load(self, *, owner_uid: str, project_id: str, publish_id: str) -> dict[str, Any]:
        return self._require(owner_uid, project_id, publish_id)

    # ------------------------------------------------------------------ worker helpers

    def mark_status(
        self,
        *,
        owner_uid: str,
        project_id: str,
        publish_id: str,
        status: PublishStatus,
        step: str | None = None,
        upload_progress: int | None = None,
        youtube_video_id: str | None = None,
        youtube_url: str | None = None,
        error: dict[str, Any] | None = None,
    ) -> None:
        data = self._require(owner_uid, project_id, publish_id)
        steps = list(data.get("steps") or [])
        if step and (not steps or steps[-1] != step):
            steps.append(step)
        changes: dict[str, Any] = {
            "status": status.value,
            "steps": steps,
            "updatedAt": datetime.now(UTC),
        }
        if upload_progress is not None:
            changes["uploadProgress"] = max(0, min(100, upload_progress))
        if youtube_video_id:
            changes["youtubeVideoId"] = youtube_video_id
        if youtube_url:
            changes["youtubeUrl"] = youtube_url
        if error is not None:
            changes["error"] = error
        self.client.update_document(publish_path(owner_uid, project_id, publish_id), changes)
        if status == PublishStatus.published:
            # The video is out: linked calendar entries stop being plans and become history.
            from app.services.schedule_service import ScheduleService

            ScheduleService(self.client, projects=self.projects).mark_linked_published(
                owner_uid=owner_uid, project_id=project_id, publish_id=publish_id
            )
        elif status == PublishStatus.deleted:
            # Gone from YouTube: its calendar slot is no longer a live post.
            from app.services.schedule_service import ScheduleService

            ScheduleService(self.client, projects=self.projects).mark_linked_cancelled(
                owner_uid=owner_uid, project_id=project_id, publish_id=publish_id
            )
        elif status == PublishStatus.failed:
            # Died: the calendar slot must say so, not keep promising a go-live.
            from app.services.schedule_service import ScheduleService

            ScheduleService(self.client, projects=self.projects).mark_linked_failed(
                owner_uid=owner_uid,
                project_id=project_id,
                publish_id=publish_id,
                message=(error or {}).get("message") if isinstance(error, dict) else None,
            )

    def _require(self, owner_uid: str, project_id: str, publish_id: str) -> dict[str, Any]:
        self.projects.get(owner_uid=owner_uid, project_id=project_id)
        data = self.client.get_document(publish_path(owner_uid, project_id, publish_id))
        if data is None or data.get("ownerUid") != owner_uid:
            raise NotFoundError("Publish not found", details={"publishId": publish_id})
        return data


def accepted(publish: Publish, job: Job) -> PublishAccepted:
    return PublishAccepted(
        publishId=publish.publishId, jobId=job.jobId, status=job.status.value
    )


def is_terminal(publish: Publish) -> bool:
    return publish.status in (PublishStatus.published, PublishStatus.failed)
