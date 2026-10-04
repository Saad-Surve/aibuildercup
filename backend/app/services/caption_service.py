"""Caption render records.

A *caption render* is one request to burn a project's transcript onto its source video with a
chosen `CaptionStyle`. Records live at
`users/{uid}/projects/{projectId}/captionRenders/{captionRenderId}` and the media under
`users/{uid}/projects/{projectId}/renders/captions/`, so the existing project delete (Firestore
subtree + storage prefix) covers them with no extra wiring.

The service only owns persistence and the job hand-off; `caption_worker` does the FFmpeg work.
"""

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

from app.errors import BadRequestError, NotFoundError
from app.schemas.captions import (
    CaptionRender,
    CaptionRenderRequest,
    CaptionRenderStatus,
    CaptionStyle,
)
from app.schemas.jobs import Job, JobType
from app.schemas.localizations import LocalizationStatus
from app.services.firestore_service import (
    FirestoreClient,
    asset_path,
    assets_collection_path,
    caption_render_object_path,
    caption_render_path,
    caption_renders_collection_path,
    localization_path,
    project_path,
)
from app.services.job_service import JobService
from app.services.project_service import ProjectService
from app.services.storage_service import StorageClient
from app.services.transcript_service import TranscriptService


def is_owner(document: dict[str, Any], owner_uid: str) -> bool:
    return document.get("ownerUid") == owner_uid


def _style_from(data: dict[str, Any]) -> CaptionStyle:
    raw = data.get("style")
    if isinstance(raw, dict):
        try:
            return CaptionStyle.model_validate(raw)
        except Exception:  # noqa: BLE001 - a corrupt style must not break listing
            return CaptionStyle()
    return CaptionStyle()


def _to_render(
    render_id: str,
    data: dict[str, Any],
    *,
    download_url: str | None = None,
) -> CaptionRender:
    return CaptionRender(
        captionRenderId=render_id,
        projectId=data.get("projectId", ""),
        status=CaptionRenderStatus(data.get("status", CaptionRenderStatus.queued.value)),
        style=_style_from(data),
        sourceAssetId=data.get("sourceAssetId"),
        sourceTranscriptId=data.get("sourceTranscriptId"),
        transcriptVersion=data.get("transcriptVersion"),
        localizationId=data.get("localizationId"),
        fileName=data.get("fileName"),
        storagePath=data.get("storagePath"),
        assStoragePath=data.get("assStoragePath"),
        mimeType=data.get("mimeType", "video/mp4"),
        sizeBytes=int(data.get("sizeBytes") or 0),
        durationMs=int(data.get("durationMs") or 0),
        width=int(data.get("width") or 0),
        height=int(data.get("height") or 0),
        jobId=data.get("jobId"),
        error=data.get("error"),
        downloadUrl=download_url,
        createdAt=data["createdAt"],
        updatedAt=data["updatedAt"],
    )


class CaptionRenderService:
    def __init__(
        self,
        client: FirestoreClient,
        *,
        projects: ProjectService,
        jobs: JobService,
        transcripts: TranscriptService,
        storage: StorageClient,
        url_ttl_seconds: int = 900,
    ) -> None:
        self.client = client
        self.projects = projects
        self.jobs = jobs
        self.transcripts = transcripts
        self.storage = storage
        self.url_ttl_seconds = url_ttl_seconds

    # ------------------------------------------------------------------- public API

    def create(
        self, *, owner_uid: str, project_id: str, payload: CaptionRenderRequest
    ) -> tuple[CaptionRender, Job]:
        """Validate the source (transcript or dub) and queue a render job."""
        self.projects.get(owner_uid=owner_uid, project_id=project_id)

        localization_id: str | None = None
        dub_video_path: str | None = None
        dub_captions_path: str | None = None
        source_asset_id: str | None = None
        source_transcript_id: str | None = None
        duration_ms = 0

        if payload.localizationId:
            # Burn a finished dub's localized captions onto its dubbed video.
            localization_id = payload.localizationId
            localization = self.client.get_document(
                localization_path(owner_uid, project_id, localization_id)
            )
            if localization is None or not is_owner(localization, owner_uid):
                raise NotFoundError(
                    "Localization not found",
                    details={"localizationId": localization_id},
                )
            if localization.get("status") != LocalizationStatus.ready.value:
                raise BadRequestError(
                    "The dub is not ready yet.",
                    code="LOCALIZATION_NOT_READY",
                    details={"localizationId": localization_id},
                )
            dub_video_path = localization.get("videoStoragePath")
            dub_captions_path = localization.get("captionsStoragePath")
            if not dub_video_path:
                raise BadRequestError(
                    "The dub has no video to caption.",
                    code="LOCALIZATION_NOT_READY",
                    details={"localizationId": localization_id},
                )
            duration_ms = int(localization.get("durationMs") or 0)
        else:
            raw_project = self.client.get_document(
                project_path(owner_uid, project_id)
            ) or {}
            source_asset_id = raw_project.get(
                "sourceAssetId"
            ) or self._first_source_asset(owner_uid=owner_uid, project_id=project_id)
            if not source_asset_id:
                raise BadRequestError(
                    "This project has no source video to render.",
                    code="SOURCE_NOT_FOUND",
                    details={"projectId": project_id},
                )
            asset = self.client.get_document(
                asset_path(owner_uid, project_id, source_asset_id)
            )
            if asset is None or not is_owner(asset, owner_uid):
                raise NotFoundError(
                    "Source video not found", details={"projectId": project_id}
                )
            transcript = self.transcripts.get(
                owner_uid=owner_uid,
                project_id=project_id,
                version=payload.transcriptVersion,
            )
            source_transcript_id = transcript.transcriptId
            duration_ms = transcript.durationMs

        render_id = uuid4().hex
        now = datetime.now(UTC)
        document: dict[str, Any] = {
            "ownerUid": owner_uid,
            "projectId": project_id,
            "status": CaptionRenderStatus.queued.value,
            "style": payload.style.model_dump(mode="json"),
            "sourceAssetId": source_asset_id,
            "sourceTranscriptId": source_transcript_id,
            "transcriptVersion": payload.transcriptVersion,
            "localizationId": localization_id,
            "dubVideoStoragePath": dub_video_path,
            "dubCaptionsStoragePath": dub_captions_path,
            "fileName": (payload.fileName or "").strip() or None,
            "storagePath": None,
            "assStoragePath": None,
            "mimeType": "video/mp4",
            "sizeBytes": 0,
            "durationMs": duration_ms,
            "width": 0,
            "height": 0,
            "jobId": None,
            "error": None,
            "createdAt": now,
            "updatedAt": now,
        }
        path = caption_render_path(owner_uid, project_id, render_id)
        self.client.set_document(path, document)

        job = self.jobs.create(
            owner_uid=owner_uid,
            project_id=project_id,
            job_type=JobType.caption_render,
            idempotency_key=f"caption-render-{project_id}-{render_id}",
            input={"captionRenderId": render_id},
        )
        self.client.update_document(
            path, {"jobId": job.jobId, "updatedAt": now}
        )
        document["jobId"] = job.jobId
        return _to_render(render_id, document), job

    def list(self, *, owner_uid: str, project_id: str) -> list[CaptionRender]:
        self.projects.get(owner_uid=owner_uid, project_id=project_id)
        rows = self.client.query_collection(
            caption_renders_collection_path(owner_uid, project_id),
            filters=[],
            order_by=[("createdAt", "DESCENDING")],
            limit=50,
            offset=0,
        )
        renders = [
            _to_render(render_id, data, download_url=self._maybe_download_url(data))
            for render_id, data in rows
            if is_owner(data, owner_uid)
        ]
        return renders

    def get(
        self, *, owner_uid: str, project_id: str, caption_render_id: str
    ) -> CaptionRender:
        data = self._require_owned(
            owner_uid=owner_uid,
            project_id=project_id,
            caption_render_id=caption_render_id,
        )
        return _to_render(
            caption_render_id, data, download_url=self._maybe_download_url(data)
        )

    def download_url(
        self, *, owner_uid: str, project_id: str, caption_render_id: str
    ) -> tuple[str, datetime]:
        """Signed read URL for a ready render, plus its expiry."""
        data = self._require_owned(
            owner_uid=owner_uid,
            project_id=project_id,
            caption_render_id=caption_render_id,
        )
        path = data.get("storagePath")
        if data.get("status") != CaptionRenderStatus.ready.value or not path:
            raise BadRequestError(
                "The captioned video is not ready yet.",
                code="CAPTION_RENDER_NOT_READY",
                details={"captionRenderId": caption_render_id},
            )
        ttl = self.url_ttl_seconds
        url = self.storage.signed_download_url(str(path), expires_seconds=ttl)
        return url, datetime.now(UTC) + timedelta(seconds=ttl)

    def delete(
        self, *, owner_uid: str, project_id: str, caption_render_id: str
    ) -> None:
        """Remove a render's media and record. Idempotent."""
        data = self._require_owned(
            owner_uid=owner_uid,
            project_id=project_id,
            caption_render_id=caption_render_id,
        )
        for key in ("storagePath", "assStoragePath"):
            path = data.get(key)
            if path:
                try:
                    self.storage.delete_prefix(str(path))
                except Exception:  # noqa: BLE001 - the record delete must still proceed
                    pass
        self.client.delete_document(
            caption_render_path(owner_uid, project_id, caption_render_id)
        )

    # ------------------------------------------------------------------- worker API

    def load(
        self, *, owner_uid: str, project_id: str, caption_render_id: str
    ) -> dict[str, Any] | None:
        """Raw render document for the worker (ownership checked)."""
        data = self.client.get_document(
            caption_render_path(owner_uid, project_id, caption_render_id)
        )
        if data is None or not is_owner(data, owner_uid):
            return None
        return data

    def target_paths(
        self, *, owner_uid: str, project_id: str, caption_render_id: str
    ) -> tuple[str, str]:
        return (
            caption_render_object_path(
                owner_uid, project_id, caption_render_id, "mp4"
            ),
            caption_render_object_path(owner_uid, project_id, caption_render_id, "ass"),
        )

    def mark_rendering(
        self, *, owner_uid: str, project_id: str, caption_render_id: str
    ) -> None:
        self.client.update_document(
            caption_render_path(owner_uid, project_id, caption_render_id),
            {"status": CaptionRenderStatus.rendering.value, "updatedAt": datetime.now(UTC)},
        )

    def mark_ready(
        self,
        *,
        owner_uid: str,
        project_id: str,
        caption_render_id: str,
        storage_path: str,
        ass_storage_path: str,
        size_bytes: int,
        duration_ms: int,
        width: int,
        height: int,
    ) -> None:
        self.client.update_document(
            caption_render_path(owner_uid, project_id, caption_render_id),
            {
                "status": CaptionRenderStatus.ready.value,
                "storagePath": storage_path,
                "assStoragePath": ass_storage_path,
                "sizeBytes": size_bytes,
                "durationMs": duration_ms,
                "width": width,
                "height": height,
                "error": None,
                "updatedAt": datetime.now(UTC),
            },
        )

    def mark_failed(
        self,
        *,
        owner_uid: str,
        project_id: str,
        caption_render_id: str,
        code: str,
        message: str,
    ) -> None:
        self.client.update_document(
            caption_render_path(owner_uid, project_id, caption_render_id),
            {
                "status": CaptionRenderStatus.failed.value,
                "error": {"code": code, "message": message},
                "updatedAt": datetime.now(UTC),
            },
        )

    # ------------------------------------------------------------------- internals

    def _maybe_download_url(self, data: dict[str, Any]) -> str | None:
        if data.get("status") != CaptionRenderStatus.ready.value:
            return None
        path = data.get("storagePath")
        if not path:
            return None
        try:
            return self.storage.signed_download_url(
                str(path), expires_seconds=self.url_ttl_seconds
            )
        except Exception:  # noqa: BLE001 - a signing hiccup must not hide the render
            return None

    def _first_source_asset(self, *, owner_uid: str, project_id: str) -> str | None:
        rows = self.client.query_collection(
            assets_collection_path(owner_uid, project_id),
            filters=[],
            order_by=[],
            limit=50,
            offset=0,
        )
        for asset_id, data in rows:
            if is_owner(data, owner_uid) and data.get("type") == "source_video":
                return asset_id
        return None

    def _require_owned(
        self, *, owner_uid: str, project_id: str, caption_render_id: str
    ) -> dict[str, Any]:
        self.projects.get(owner_uid=owner_uid, project_id=project_id)
        data = self.client.get_document(
            caption_render_path(owner_uid, project_id, caption_render_id)
        )
        if data is None or not is_owner(data, owner_uid):
            raise NotFoundError(
                "Caption render not found",
                details={"captionRenderId": caption_render_id},
            )
        return data
