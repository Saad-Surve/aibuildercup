"""Project-scoped packaging records, jobs and bounded paid render reservations."""

from datetime import UTC, datetime
from threading import RLock
from typing import Any
from uuid import uuid4

from app.config import Settings
from app.errors import BadRequestError, ConflictError, NotFoundError
from app.schemas.jobs import Job, JobStatus, JobType
from app.schemas.packaging import (
    ListingFields,
    PackagingBrief,
    PackagingListing,
    RenderVisualInsertRequest,
    VisualInsert,
    VisualInsertList,
)
from app.services.firestore_service import FirestoreClient
from app.services.job_service import JobService
from app.services.paths import project_object_prefix, project_path, safe_segment
from app.services.project_service import ProjectService
from app.services.storage_service import StorageClient
from app.services.transcript_service import TranscriptService

# The app's worker deployment is one instance. Atomic paid slot creation also protects
# the monetary bound across processes; this lock serializes ordinary UI actions locally.
_actions = RLock()


def packaging_path(uid: str, project_id: str, name: str) -> str:
    return f"{project_path(uid, project_id)}/packaging/{safe_segment(name, name='name')}"


def insert_path(uid: str, project_id: str, insert_id: str) -> str:
    return (
        f"{project_path(uid, project_id)}/visualInserts/{safe_segment(insert_id, name='insertId')}"
    )


def insert_prefix(uid: str, project_id: str, insert_id: str) -> str:
    return (
        f"{project_object_prefix(uid, project_id)}visual-inserts/"
        f"{safe_segment(insert_id, name='insertId')}/"
    )


class PackagingService:
    def __init__(
        self,
        client: FirestoreClient,
        *,
        projects: ProjectService,
        jobs: JobService,
        transcripts: TranscriptService,
        storage: StorageClient,
        settings: Settings,
    ) -> None:
        self.client = client
        self.projects = projects
        self.jobs = jobs
        self.transcripts = transcripts
        self.storage = storage
        self.settings = settings

    def source(self, uid: str, project_id: str) -> tuple[str, str]:
        project = self.projects.get(owner_uid=uid, project_id=project_id)
        if not project.sourceAssetId:
            raise ConflictError("Upload a video before generating packaging.")
        transcript = self.transcripts.get(owner_uid=uid, project_id=project_id)
        if not transcript.segments or transcript.durationMs <= 0:
            raise ConflictError("Finish transcription before generating packaging.")
        return project.sourceAssetId, transcript.transcriptId

    def stale(self, uid: str, project_id: str, data: dict[str, Any]) -> bool:
        try:
            source, transcript = self.source(uid, project_id)
        except (NotFoundError, ConflictError):
            return True
        return source != data.get("sourceAssetId") or transcript != data.get("transcriptId")

    def listing(self, uid: str, project_id: str) -> PackagingListing | None:
        self.projects.get(owner_uid=uid, project_id=project_id)
        data = self.client.get_document(packaging_path(uid, project_id, "listing"))
        if not data or data.get("ownerUid") != uid:
            return None
        return PackagingListing.model_validate({**data, "stale": self.stale(uid, project_id, data)})

    def save_listing(self, uid: str, project_id: str, fields: ListingFields) -> PackagingListing:
        with _actions:
            current = self.listing(uid, project_id)
            if current and current.status in ("queued", "generating"):
                raise ConflictError("Wait for listing generation to finish before saving edits.")
            if current and current.stale:
                raise ConflictError("The source changed. Generate a new listing before saving.")
            source, transcript = self.source(uid, project_id)
            data = {
                **(current.model_dump(exclude={"stale"}) if current else {}),
                **fields.model_dump(),
                "ownerUid": uid,
                "sourceAssetId": source,
                "transcriptId": transcript,
                "status": "ready",
                "error": None,
                "updatedAt": datetime.now(UTC),
            }
            self.write(uid, project_id, packaging_path(uid, project_id, "listing"), data)
            return PackagingListing.model_validate(data)

    def generate(self, uid: str, project_id: str, mode: str, brief: PackagingBrief) -> Job:
        with _actions:
            source, transcript = self.source(uid, project_id)
            target = "listing" if mode == "listing" else "insertSuggestions"
            path = packaging_path(uid, project_id, target)
            existing = self.client.get_document(path) or {}
            if existing.get("ownerUid") == uid and existing.get("jobId"):
                job = self.jobs.get(owner_uid=uid, job_id=existing["jobId"])
                if job.status in (JobStatus.queued, JobStatus.running):
                    return job
            job = self.jobs.create(
                owner_uid=uid,
                project_id=project_id,
                job_type=JobType.text_content if mode == "listing" else JobType.clip,
                idempotency_key=f"packaging:{mode}:{uuid4().hex}",
                requested_by=uid,
                input={
                    "mode": mode,
                    "sourceAssetId": source,
                    "transcriptId": transcript,
                    **brief.model_dump(),
                },
            )
            if mode == "listing":
                project = self.projects.get(owner_uid=uid, project_id=project_id)
                existing.setdefault(
                    "title",
                    project.name[:100].replace("<", "").replace(">", "").strip()
                    or "Untitled video",
                )
            self.write(
                uid,
                project_id,
                path,
                {
                    **existing,
                    "ownerUid": uid,
                    "sourceAssetId": source,
                    "transcriptId": transcript,
                    "jobId": job.jobId,
                    "status": "queued",
                    "error": None,
                    "updatedAt": datetime.now(UTC),
                },
            )
            return job

    def load_insert(self, uid: str, project_id: str, insert_id: str) -> dict[str, Any]:
        self.projects.get(owner_uid=uid, project_id=project_id)
        data = self.client.get_document(insert_path(uid, project_id, insert_id))
        if not data or data.get("ownerUid") != uid:
            raise NotFoundError("Visual insert not found.")
        return data

    def list_inserts(self, uid: str, project_id: str) -> VisualInsertList:
        self.projects.get(owner_uid=uid, project_id=project_id)
        rows = self.client.query_collection(
            f"{project_path(uid, project_id)}/visualInserts",
            filters=[],
            order_by=[("createdAt", "DESCENDING")],
            limit=60,
            offset=0,
        )
        items = []
        current: tuple[str, str] | None = None
        try:
            current = self.source(uid, project_id)
        except (NotFoundError, ConflictError):
            pass
        for insert_id, data in rows:
            if data.get("ownerUid") != uid:
                continue
            url = None
            reference_url = None
            if data.get("styleReferencePath"):
                reference_url = self.storage.signed_download_url(
                    data["styleReferencePath"], expires_seconds=self.settings.upload_url_ttl_seconds
                )
            if data.get("status") == "ready" and data.get("storagePath"):
                url = self.storage.signed_download_url(
                    data["storagePath"], expires_seconds=self.settings.upload_url_ttl_seconds
                )
            items.append(
                VisualInsert.model_validate(
                    {
                        **data,
                        "insertId": insert_id,
                        "previewUrl": url,
                        "styleReferenceUrl": reference_url,
                        "canRetry": not data.get("operationFinished")
                        and not (data.get("submissionStarted") and not data.get("operationName")),
                        "stale": current != (data.get("sourceAssetId"), data.get("transcriptId")),
                    }
                )
            )
        suggestions = self.client.get_document(packaging_path(uid, project_id, "insertSuggestions"))
        return VisualInsertList(
            items=items,
            suggestionJobId=(suggestions or {}).get("jobId"),
            paidRendersRemaining=sum(
                self.client.get_document(self._slot_path(uid, project_id, i)) is None
                for i in range(self.paid_limit)
            ),
        )

    @property
    def paid_limit(self) -> int:
        cost = 6 * self.settings.videogen_price_per_second_usd
        return min(
            self.settings.visual_insert_max_paid_renders,
            int(self.settings.max_project_cost_usd / cost),
        )

    def _slot_path(self, uid: str, project_id: str, index: int) -> str:
        return f"{project_path(uid, project_id)}/visualInsertReservations/slot-{index}"

    def render(
        self,
        uid: str,
        project_id: str,
        insert_id: str,
        request: RenderVisualInsertRequest,
    ) -> Job:
        with _actions:
            data = self.load_insert(uid, project_id, insert_id)
            if self.stale(uid, project_id, data):
                raise ConflictError("The video or transcript changed. Suggest new visual inserts.")
            if data.get("jobId"):
                job = self.jobs.get(owner_uid=uid, job_id=data["jobId"])
                if job.status in (JobStatus.queued, JobStatus.running, JobStatus.succeeded):
                    return job
            paid = data["kind"] == "broll"
            if paid and not data.get("operationName"):
                if not data.get("visualStyle") or not data.get("directionVersion"):
                    raise ConflictError(
                        "Suggest new inserts to match the source video's visual style."
                    )
                if data.get(
                    "generationMode"
                ) == "image-to-video" and request.aspectRatio != data.get("referenceAspectRatio"):
                    raise BadRequestError(
                        "Source-frame footage keeps the source frame's aspect ratio."
                    )
            if data.get("operationFinished"):
                raise ConflictError(
                    "This video operation failed. Suggest a new insert to try again."
                )
            if paid and not request.allowPaidGeneration:
                raise BadRequestError("Choose the paid render action to generate footage.")
            if request.prompt is not None and not paid:
                raise BadRequestError("Chart and callout content comes from the source transcript.")
            if data.get("submissionStarted") and not data.get("operationName"):
                raise ConflictError(
                    "The previous video submission could not be confirmed. "
                    "It will not be submitted again; suggest a new insert if needed.",
                    code="VIDEO_SUBMISSION_UNCONFIRMED",
                )
            if data.get("operationName"):
                if request.prompt is not None and request.prompt != data.get("prompt"):
                    raise ConflictError("A submitted clip's prompt cannot change on retry.")
                if request.aspectRatio != data.get("aspectRatio"):
                    raise ConflictError("A submitted clip's aspect ratio cannot change on retry.")
            if paid and data.get("paidSlot") is None:
                for i in range(self.paid_limit):
                    if self.client.set_owned_child(
                        project_path(uid, project_id),
                        self._slot_path(uid, project_id, i),
                        uid,
                        {
                            "ownerUid": uid,
                            "insertId": insert_id,
                            "createdAt": datetime.now(UTC),
                            "reservedCostUsd": 6 * self.settings.videogen_price_per_second_usd,
                        },
                        create_only=True,
                    ):
                        data["paidSlot"] = i
                        break
                else:
                    raise ConflictError(
                        "This project's paid clip allowance is used up.",
                        code="VISUAL_INSERT_BUDGET_EXCEEDED",
                    )
            job = self.jobs.create(
                owner_uid=uid,
                project_id=project_id,
                job_type=JobType.veo if paid else JobType.clip,
                idempotency_key=f"insert-render:{insert_id}:{uuid4().hex}",
                requested_by=uid,
                input={"mode": "render", "insertId": insert_id},
            )
            self.write(
                uid,
                project_id,
                insert_path(uid, project_id, insert_id),
                {
                    **data,
                    "jobId": job.jobId,
                    "status": "queued",
                    "error": None,
                    "aspectRatio": request.aspectRatio,
                    "prompt": request.prompt if request.prompt is not None else data["prompt"],
                },
            )
            return job

    def delete_insert(self, uid: str, project_id: str, insert_id: str) -> None:
        with _actions:
            data = self.load_insert(uid, project_id, insert_id)
            if data["status"] in ("queued", "rendering"):
                raise ConflictError("Wait for the render to finish before deleting this insert.")
            if (
                data.get("operationName")
                and data["status"] == "failed"
                and not data.get("operationFinished")
            ):
                raise ConflictError(
                    "Resume the pending video operation before deleting its record."
                )
            self.storage.delete_prefix(insert_prefix(uid, project_id, insert_id))
            self.client.delete_document(insert_path(uid, project_id, insert_id))

    def write(self, uid: str, project_id: str, path: str, data: dict[str, Any]) -> None:
        if not self.client.set_owned_child(project_path(uid, project_id), path, uid, data):
            raise NotFoundError("Project no longer exists.")
