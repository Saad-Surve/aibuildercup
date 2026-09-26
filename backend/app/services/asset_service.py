"""Project assets: create a direct-to-Cloud-Storage upload session and confirm uploads.

The browser uploads straight to Cloud Storage with a short-lived signed URL; the API only
issues the URL, then verifies the object exists and records the asset. Confirming an upload
queues the first pipeline job (transcription), which is idempotent per asset.
"""

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

from app.config import Settings
from app.errors import BadRequestError, NotFoundError
from app.schemas.assets import (
    Asset,
    AssetStatus,
    AssetType,
    CreateUploadSession,
    DownloadUrl,
    UploadSession,
)
from app.schemas.jobs import Job, JobStatus, JobType
from app.services.firestore_service import (
    FirestoreClient,
    asset_path,
    assets_collection_path,
    project_path,
    source_object_path,
)
from app.services.job_service import JobService
from app.services.project_service import ProjectService
from app.services.storage_service import StorageClient

# Allowed source video content types mapped to the object extension.
ALLOWED_SOURCE_TYPES: dict[str, str] = {
    "video/mp4": "mp4",
    "video/quicktime": "mov",
    "video/webm": "webm",
    "video/x-m4v": "m4v",
}


def is_owner(document: dict[str, Any], owner_uid: str) -> bool:
    return document.get("ownerUid") == owner_uid


def _to_asset(asset_id: str, data: dict[str, Any]) -> Asset:
    return Asset(
        assetId=asset_id,
        projectId=data.get("projectId", ""),
        type=AssetType(data.get("type", AssetType.source_video.value)),
        status=AssetStatus(data.get("status", AssetStatus.pending.value)),
        storagePath=data.get("storagePath", ""),
        mimeType=data.get("mimeType", ""),
        sizeBytes=data.get("sizeBytes", 0),
        durationMs=data.get("durationMs"),
        createdAt=data["createdAt"],
        updatedAt=data["updatedAt"],
    )


class AssetService:
    def __init__(
        self,
        client: FirestoreClient,
        *,
        projects: ProjectService,
        jobs: JobService,
        storage: StorageClient,
        settings: Settings,
    ) -> None:
        self.client = client
        self.projects = projects
        self.jobs = jobs
        self.storage = storage
        self.settings = settings

    def create_upload_session(
        self, *, owner_uid: str, project_id: str, payload: CreateUploadSession
    ) -> UploadSession:
        self.projects.get(owner_uid=owner_uid, project_id=project_id)

        content_type = payload.contentType.strip().lower()
        extension = ALLOWED_SOURCE_TYPES.get(content_type)
        if extension is None:
            raise BadRequestError(
                "Unsupported video format.",
                code="UNSUPPORTED_MEDIA_TYPE",
                details={
                    "contentType": content_type,
                    "allowed": sorted(ALLOWED_SOURCE_TYPES),
                },
            )
        if payload.sizeBytes > self.settings.max_upload_size_bytes:
            raise BadRequestError(
                "Video exceeds the maximum upload size.",
                code="FILE_TOO_LARGE",
                details={
                    "sizeBytes": payload.sizeBytes,
                    "maxBytes": self.settings.max_upload_size_bytes,
                },
            )

        asset_id = uuid4().hex
        storage_path = source_object_path(owner_uid, project_id, asset_id, extension)

        # Generate the URL before persisting anything: if signing fails there is no asset record
        # left behind to clutter the workspace.
        ttl = self.settings.upload_url_ttl_seconds
        upload_url = self.storage.signed_upload_url(
            storage_path, content_type=content_type, expires_seconds=ttl
        )

        now = datetime.now(UTC)
        document: dict[str, Any] = {
            "ownerUid": owner_uid,
            "projectId": project_id,
            "type": AssetType.source_video.value,
            "status": AssetStatus.pending.value,
            "storagePath": storage_path,
            "mimeType": content_type,
            "sizeBytes": payload.sizeBytes,
            "checksum": None,
            "durationMs": None,
            "width": None,
            "height": None,
            "frameRate": None,
            "language": None,
            "derivedFromAssetId": None,
            "createdAt": now,
            "updatedAt": now,
            "deletedAt": None,
        }
        self.client.set_document(asset_path(owner_uid, project_id, asset_id), document)

        return UploadSession(
            assetId=asset_id,
            storagePath=storage_path,
            uploadUrl=upload_url,
            expiresAt=now + timedelta(seconds=ttl),
            requiredHeaders={"Content-Type": content_type},
        )

    def complete_upload(self, *, owner_uid: str, project_id: str, asset_id: str) -> Job:
        data = self._require_owned_asset(
            owner_uid=owner_uid, project_id=project_id, asset_id=asset_id
        )
        storage_path = data["storagePath"]
        if not self.storage.object_exists(storage_path):
            raise BadRequestError(
                "The upload was not found in storage.",
                code="UPLOAD_NOT_FOUND",
                details={"assetId": asset_id},
            )
        return self.queue_transcription(
            owner_uid=owner_uid, project_id=project_id, asset_id=asset_id, retry_failed=True
        )

    def queue_transcription(
        self,
        *,
        owner_uid: str,
        project_id: str,
        asset_id: str,
        retry_failed: bool = False,
    ) -> Job:
        """Idempotently mark the asset uploaded, the project processing, and queue transcribe.

        Shared by `POST /assets/{id}/complete` (UX) and the GCS-finalized Pub/Sub handler
        (trigger of record), so both paths converge on the same job record. The UX path asks
        to retry a failed job (`retry_failed=True`); the Pub/Sub path stays a pure no-op when
        the job already exists, so a redelivered event can never restart a finished run.
        """
        self._require_owned_asset(
            owner_uid=owner_uid, project_id=project_id, asset_id=asset_id
        )
        job = self.jobs.create(
            owner_uid=owner_uid,
            project_id=project_id,
            job_type=JobType.transcribe,
            idempotency_key=f"transcribe-{project_id}-{asset_id}-v1",
            input={"assetId": asset_id},
        )
        if retry_failed and job.status == JobStatus.failed:
            job = self.jobs.requeue_failed(
                owner_uid=owner_uid,
                project_id=project_id,
                job_id=job.jobId,
                input={"assetId": asset_id},
            )
        # A finished or already-running job owns the asset/project state: do not drag a ready
        # project back to `processing` (which used to strand a re-completed upload).
        if job.status in (JobStatus.succeeded, JobStatus.running):
            return job
        now = datetime.now(UTC)
        self.client.update_document(
            asset_path(owner_uid, project_id, asset_id),
            {"status": AssetStatus.uploaded.value, "updatedAt": now},
        )
        self.projects.mark_processing(
            owner_uid=owner_uid, project_id=project_id, source_asset_id=asset_id
        )
        return job

    def retranscribe_source(self, *, owner_uid: str, project_id: str) -> Job:
        """Queue a fresh transcribe job for the project's source video.

        Re-completing the upload only returns the original idempotent job, so a transcript
        could never be regenerated after the first run. This mints a new job with a
        per-version key (the project's transcript version counter) instead. A double click
        before the new transcript lands maps to the same key and stays idempotent.
        """
        self.projects.get(owner_uid=owner_uid, project_id=project_id)
        source = next(
            (
                asset
                for asset in self.list(owner_uid=owner_uid, project_id=project_id)
                if asset.type == AssetType.source_video.value
            ),
            None,
        )
        if source is None:
            raise NotFoundError(
                "Source video not found", details={"projectId": project_id}
            )
        if not self.storage.object_exists(source.storagePath):
            raise BadRequestError(
                "The source video is missing from storage.",
                code="SOURCE_NOT_FOUND",
                details={"assetId": source.assetId},
            )
        raw = self.client.get_document(project_path(owner_uid, project_id)) or {}
        run = int(raw.get("transcriptVersionCounter", 0) or 0) + 1
        job = self.jobs.create(
            owner_uid=owner_uid,
            project_id=project_id,
            job_type=JobType.transcribe,
            idempotency_key=f"transcribe-{project_id}-{source.assetId}-r{run}",
            input={"assetId": source.assetId},
        )
        if job.status in (JobStatus.succeeded, JobStatus.running):
            return job
        self.projects.mark_processing(
            owner_uid=owner_uid, project_id=project_id, source_asset_id=source.assetId
        )
        return job

    def download_url(self, *, owner_uid: str, project_id: str, asset_id: str) -> DownloadUrl:
        """Short-lived signed read URL so the browser can stream the source video directly."""
        data = self._require_owned_asset(
            owner_uid=owner_uid, project_id=project_id, asset_id=asset_id
        )
        ttl = self.settings.upload_url_ttl_seconds
        now = datetime.now(UTC)
        return DownloadUrl(
            url=self.storage.signed_download_url(
                data["storagePath"], expires_seconds=ttl
            ),
            expiresAt=now + timedelta(seconds=ttl),
        )

    def list(self, *, owner_uid: str, project_id: str) -> list[Asset]:
        self.projects.get(owner_uid=owner_uid, project_id=project_id)
        rows = self.client.query_collection(
            assets_collection_path(owner_uid, project_id),
            filters=[],
            order_by=[],
            limit=100,
            offset=0,
        )
        assets = [
            _to_asset(asset_id, data)
            for asset_id, data in rows
            if data.get("deletedAt") is None and is_owner(data, owner_uid)
        ]
        assets.sort(key=lambda asset: asset.createdAt, reverse=True)
        return assets

    def _require_owned_asset(
        self, *, owner_uid: str, project_id: str, asset_id: str
    ) -> dict[str, Any]:
        self.projects.get(owner_uid=owner_uid, project_id=project_id)
        data = self.client.get_document(asset_path(owner_uid, project_id, asset_id))
        if (
            data is None
            or not is_owner(data, owner_uid)
            or data.get("deletedAt") is not None
        ):
            raise NotFoundError("Asset not found", details={"assetId": asset_id})
        return data
