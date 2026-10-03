"""Thumbnail concept records.

Owns persistence and the job hand-off; `thumbnail_worker` does the planning, frame extraction,
image generation, and critique. Records live at
`users/{uid}/projects/{projectId}/thumbnailConcepts/{thumbnailId}` and images under
`.../thumbnails/{thumbnailId}/`, so the existing project delete (Firestore subtree + storage
prefix) covers them with no extra wiring.

The only writing the API does synchronously is creating queued placeholders and applying a
concept's headline to `project.thumbnailConcept`; everything expensive is a job.
"""

import logging
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

from app.errors import BadRequestError, ConflictError, NotFoundError
from app.schemas.jobs import Job, JobType
from app.schemas.projects import UpdateProject
from app.schemas.thumbnails import (
    GenerateThumbnailsRequest,
    ReviseThumbnailRequest,
    ThumbnailConcept,
    ThumbnailCritique,
    ThumbnailStatus,
    ThumbnailVersion,
)
from app.services.firestore_service import (
    FirestoreClient,
    project_path,
    thumbnail_concept_path,
    thumbnail_concepts_collection_path,
    thumbnail_object_path,
    thumbnail_reference_object_path,
)
from app.services.job_service import JobService
from app.services.project_service import ProjectService
from app.services.storage_service import StorageClient

logger = logging.getLogger(__name__)


def is_owner(document: dict[str, Any], owner_uid: str) -> bool:
    return document.get("ownerUid") == owner_uid


def _critique_from(data: Any) -> ThumbnailCritique | None:
    if not isinstance(data, dict):
        return None
    try:
        return ThumbnailCritique.model_validate(data)
    except Exception:  # noqa: BLE001 - a corrupt critique must not break listing
        return None


def _version_from(data: dict[str, Any]) -> ThumbnailVersion | None:
    try:
        return ThumbnailVersion(
            versionId=str(data.get("versionId", "")),
            version=int(data.get("version", 0) or 0),
            storagePath=data.get("storagePath"),
            mimeType=data.get("mimeType", "image/png"),
            width=int(data.get("width") or 0),
            height=int(data.get("height") or 0),
            sizeBytes=int(data.get("sizeBytes") or 0),
            instruction=data.get("instruction", ""),
            headline=data.get("headline", ""),
            rationale=data.get("rationale", ""),
            referenceTimestampsMs=[
                int(item) for item in (data.get("referenceTimestampsMs") or [])
            ],
            critique=_critique_from(data.get("critique")),
            model=data.get("model", ""),
            costUsd=float(data.get("costUsd") or 0.0),
            createdAt=data["createdAt"],
        )
    except Exception:  # noqa: BLE001
        logger.warning("thumbnail: skipping a corrupt version", exc_info=True)
        return None


def _to_concept(
    thumbnail_id: str,
    data: dict[str, Any],
    *,
    preview_url: str | None = None,
) -> ThumbnailConcept:
    versions = [
        version
        for version in (_version_from(item) for item in (data.get("versions") or []))
        if version is not None
    ]
    versions.sort(key=lambda item: item.version)
    return ThumbnailConcept(
        thumbnailId=thumbnail_id,
        projectId=data.get("projectId", ""),
        status=ThumbnailStatus(data.get("status", ThumbnailStatus.queued.value)),
        aspect=data.get("aspect", "16:9"),
        headline=data.get("headline", ""),
        rationale=data.get("rationale", ""),
        sourceTimestampMs=data.get("sourceTimestampMs"),
        referenceTimestampsMs=[
            int(item) for item in (data.get("referenceTimestampsMs") or [])
        ],
        activeVersionId=data.get("activeVersionId"),
        versions=versions,
        isApplied=bool(data.get("isApplied")),
        jobId=data.get("jobId"),
        error=data.get("error"),
        previewUrl=preview_url,
        createdAt=data["createdAt"],
        updatedAt=data["updatedAt"],
    )


class ThumbnailService:
    def __init__(
        self,
        client: FirestoreClient,
        *,
        projects: ProjectService,
        jobs: JobService,
        storage: StorageClient,
        url_ttl_seconds: int = 900,
        price_per_image_usd: float = 0.067,
        max_project_cost_usd: float = 5.0,
    ) -> None:
        self.client = client
        self.projects = projects
        self.jobs = jobs
        self.storage = storage
        self.url_ttl_seconds = url_ttl_seconds
        self.price_per_image_usd = price_per_image_usd
        self.max_project_cost_usd = max_project_cost_usd

    # ------------------------------------------------------------------- public API

    def create_batch(
        self,
        *,
        owner_uid: str,
        project_id: str,
        payload: GenerateThumbnailsRequest,
    ) -> tuple[list[ThumbnailConcept], Job]:
        """Create queued placeholder concepts and one job that plans and renders them."""
        self.projects.get(owner_uid=owner_uid, project_id=project_id)
        self._guard_budget(owner_uid=owner_uid, project_id=project_id, new_count=payload.count)

        batch_id = uuid4().hex
        now = datetime.now(UTC)
        thumbnail_ids: list[str] = []
        concepts: list[ThumbnailConcept] = []
        for _ in range(payload.count):
            thumbnail_id = uuid4().hex
            thumbnail_ids.append(thumbnail_id)
            document: dict[str, Any] = {
                "ownerUid": owner_uid,
                "projectId": project_id,
                "status": ThumbnailStatus.queued.value,
                "aspect": payload.aspect.value,
                "headline": "",
                "rationale": "",
                "sourceTimestampMs": None,
                "referenceTimestampsMs": [],
                "activeVersionId": None,
                "versions": [],
                "isApplied": False,
                "batchId": batch_id,
                "jobId": None,
                "error": None,
                "createdAt": now,
                "updatedAt": now,
            }
            self.client.set_document(
                thumbnail_concept_path(owner_uid, project_id, thumbnail_id), document
            )
            concepts.append(_to_concept(thumbnail_id, document))

        job = self.jobs.create(
            owner_uid=owner_uid,
            project_id=project_id,
            job_type=JobType.thumbnail,
            idempotency_key=f"thumbnails-{project_id}-{batch_id}",
            input={
                "thumbnailIds": thumbnail_ids,
                "batchId": batch_id,
                "mode": "generate",
                "aspect": payload.aspect.value,
                "imageSize": payload.imageSize,
                "brief": payload.brief,
                "useRealFrames": payload.useRealFrames,
                "useProModel": payload.useProModel,
            },
        )
        for thumbnail_id in thumbnail_ids:
            self.client.update_document(
                thumbnail_concept_path(owner_uid, project_id, thumbnail_id),
                {"jobId": job.jobId},
            )
        return concepts, job

    def revise(
        self,
        *,
        owner_uid: str,
        project_id: str,
        thumbnail_id: str,
        payload: ReviseThumbnailRequest,
    ) -> tuple[ThumbnailConcept, Job]:
        """Queue a conversational edit of a concept's active image."""
        data = self._require_owned(
            owner_uid=owner_uid, project_id=project_id, thumbnail_id=thumbnail_id
        )
        if not data.get("activeVersionId"):
            raise ConflictError(
                "This concept has no image to edit yet.",
                code="THUMBNAIL_NOT_READY",
                details={"thumbnailId": thumbnail_id},
            )
        self._guard_budget(owner_uid=owner_uid, project_id=project_id, new_count=1)
        now = datetime.now(UTC)
        job = self.jobs.create(
            owner_uid=owner_uid,
            project_id=project_id,
            job_type=JobType.thumbnail,
            idempotency_key=f"thumbnail-revise-{project_id}-{thumbnail_id}-{uuid4().hex[:8]}",
            input={
                "thumbnailIds": [thumbnail_id],
                "mode": "revise",
                "instruction": payload.instruction.strip(),
            },
        )
        self.client.update_document(
            thumbnail_concept_path(owner_uid, project_id, thumbnail_id),
            {"status": ThumbnailStatus.generating.value, "jobId": job.jobId, "updatedAt": now},
        )
        data.update(
            {"status": ThumbnailStatus.generating.value, "jobId": job.jobId, "updatedAt": now}
        )
        return _to_concept(thumbnail_id, data), job

    def list(self, *, owner_uid: str, project_id: str) -> list[ThumbnailConcept]:
        self.projects.get(owner_uid=owner_uid, project_id=project_id)
        rows = self.client.query_collection(
            thumbnail_concepts_collection_path(owner_uid, project_id),
            filters=[],
            order_by=[("createdAt", "DESCENDING")],
            limit=50,
            offset=0,
        )
        concepts = [
            _to_concept(thumbnail_id, data, preview_url=self._preview_url(data))
            for thumbnail_id, data in rows
            if is_owner(data, owner_uid)
        ]
        return concepts

    def get(
        self, *, owner_uid: str, project_id: str, thumbnail_id: str
    ) -> ThumbnailConcept:
        data = self._require_owned(
            owner_uid=owner_uid, project_id=project_id, thumbnail_id=thumbnail_id
        )
        return _to_concept(thumbnail_id, data, preview_url=self._preview_url(data))

    def apply(
        self, *, owner_uid: str, project_id: str, thumbnail_id: str
    ) -> ThumbnailConcept:
        """Write this concept's headline + rationale to `project.thumbnailConcept`.

        This closes the loop: the reviewers already judge hooks against
        `thumbnailConcept`, so applying a concept makes the whole review
        packaging-aware.
        """
        data = self._require_owned(
            owner_uid=owner_uid, project_id=project_id, thumbnail_id=thumbnail_id
        )
        headline = str(data.get("headline") or "").strip()
        rationale = str(data.get("rationale") or "").strip()
        if not headline:
            raise ConflictError(
                "This concept has no headline to apply yet.",
                code="THUMBNAIL_NOT_READY",
                details={"thumbnailId": thumbnail_id},
            )
        concept_text = f"{headline} — {rationale}".strip(" —")[:500]
        # Only one concept is the applied one at a time.
        for other_id, other in self._all(owner_uid=owner_uid, project_id=project_id):
            if bool(other.get("isApplied")) != (other_id == thumbnail_id):
                self.client.update_document(
                    thumbnail_concept_path(owner_uid, project_id, other_id),
                    {"isApplied": other_id == thumbnail_id},
                )
        self.projects.update(
            owner_uid=owner_uid,
            project_id=project_id,
            patch=UpdateProject(thumbnailConcept=concept_text),
        )
        updated = self.client.get_document(
            thumbnail_concept_path(owner_uid, project_id, thumbnail_id)
        ) or data
        return _to_concept(thumbnail_id, updated, preview_url=self._preview_url(updated))

    def delete(self, *, owner_uid: str, project_id: str, thumbnail_id: str) -> None:
        """Remove a concept's images and record. Idempotent enough for a retry."""
        data = self.client.get_document(
            thumbnail_concept_path(owner_uid, project_id, thumbnail_id)
        )
        if data is None:
            return
        if not is_owner(data, owner_uid):
            raise NotFoundError(
                "Thumbnail concept not found", details={"thumbnailId": thumbnail_id}
            )
        try:
            self.storage.delete_prefix(
                f"{project_path(owner_uid, project_id)}/thumbnails/{thumbnail_id}/"
            )
        except Exception:  # noqa: BLE001 - the record delete must still proceed
            logger.warning("thumbnail: could not delete objects for %s", thumbnail_id)
        self.client.delete_document(
            thumbnail_concept_path(owner_uid, project_id, thumbnail_id)
        )

    def download_url(
        self, *, owner_uid: str, project_id: str, thumbnail_id: str
    ) -> tuple[str, datetime]:
        data = self._require_owned(
            owner_uid=owner_uid, project_id=project_id, thumbnail_id=thumbnail_id
        )
        version = self._active_version(data)
        path = version.get("storagePath") if version else None
        if not path:
            raise BadRequestError(
                "The thumbnail image is not ready yet.",
                code="THUMBNAIL_NOT_READY",
                details={"thumbnailId": thumbnail_id},
            )
        ttl = self.url_ttl_seconds
        url = self.storage.signed_download_url(str(path), expires_seconds=ttl)
        return url, datetime.now(UTC) + timedelta(seconds=ttl)

    # ------------------------------------------------------------------- worker API

    def load(
        self, *, owner_uid: str, project_id: str, thumbnail_id: str
    ) -> dict[str, Any] | None:
        data = self.client.get_document(
            thumbnail_concept_path(owner_uid, project_id, thumbnail_id)
        )
        if data is None or not is_owner(data, owner_uid):
            return None
        return data

    def mark_generating(
        self, *, owner_uid: str, project_id: str, thumbnail_id: str, headline: str = ""
    ) -> None:
        changes: dict[str, Any] = {
            "status": ThumbnailStatus.generating.value,
            "updatedAt": datetime.now(UTC),
        }
        if headline:
            changes["headline"] = headline
        self.client.update_document(
            thumbnail_concept_path(owner_uid, project_id, thumbnail_id), changes
        )

    def save_plan(
        self,
        *,
        owner_uid: str,
        project_id: str,
        thumbnail_id: str,
        headline: str,
        rationale: str,
        source_timestamp_ms: int | None,
    ) -> None:
        self.client.update_document(
            thumbnail_concept_path(owner_uid, project_id, thumbnail_id),
            {
                "headline": headline,
                "rationale": rationale,
                "sourceTimestampMs": source_timestamp_ms,
                "updatedAt": datetime.now(UTC),
            },
        )

    def add_version(
        self,
        *,
        owner_uid: str,
        project_id: str,
        thumbnail_id: str,
        version: ThumbnailVersion,
    ) -> None:
        data = self.load(
            owner_uid=owner_uid, project_id=project_id, thumbnail_id=thumbnail_id
        ) or {}
        versions = list(data.get("versions") or [])
        versions.append(version.model_dump(mode="json"))
        self.client.update_document(
            thumbnail_concept_path(owner_uid, project_id, thumbnail_id),
            {
                "versions": versions,
                "activeVersionId": version.versionId,
                "referenceTimestampsMs": version.referenceTimestampsMs,
                "status": ThumbnailStatus.ready.value,
                "error": None,
                "updatedAt": datetime.now(UTC),
            },
        )

    def mark_failed(
        self,
        *,
        owner_uid: str,
        project_id: str,
        thumbnail_id: str,
        code: str,
        message: str,
    ) -> None:
        self.client.update_document(
            thumbnail_concept_path(owner_uid, project_id, thumbnail_id),
            {
                "status": ThumbnailStatus.failed.value,
                "error": {"code": code, "message": message},
                "updatedAt": datetime.now(UTC),
            },
        )

    def target_paths(
        self,
        *,
        owner_uid: str,
        project_id: str,
        thumbnail_id: str,
        version: int,
        extension: str,
    ) -> str:
        return thumbnail_object_path(
            owner_uid, project_id, thumbnail_id, version, extension
        )

    def reference_path(
        self,
        *,
        owner_uid: str,
        project_id: str,
        thumbnail_id: str,
        timestamp_ms: int,
    ) -> str:
        return thumbnail_reference_object_path(
            owner_uid, project_id, thumbnail_id, timestamp_ms
        )

    def spend_usd(self, *, owner_uid: str, project_id: str) -> float:
        total = 0.0
        for _, data in self._all(owner_uid=owner_uid, project_id=project_id):
            for version in data.get("versions") or []:
                total += float(version.get("costUsd") or 0.0)
        return round(total, 6)

    # ------------------------------------------------------------------- internals

    def _guard_budget(
        self, *, owner_uid: str, project_id: str, new_count: int
    ) -> None:
        spent = self.spend_usd(owner_uid=owner_uid, project_id=project_id)
        projected = spent + new_count * self.price_per_image_usd
        if projected > self.max_project_cost_usd:
            raise ConflictError(
                "This project has reached its image-generation budget.",
                code="THUMBNAIL_BUDGET_EXCEEDED",
                details={
                    "spentUsd": spent,
                    "maxProjectCostUsd": self.max_project_cost_usd,
                },
            )

    def _all(
        self, *, owner_uid: str, project_id: str
    ) -> Sequence[tuple[str, dict[str, Any]]]:
        rows = self.client.query_collection(
            thumbnail_concepts_collection_path(owner_uid, project_id),
            filters=[],
            order_by=[],
            limit=50,
            offset=0,
        )
        return [
            (thumbnail_id, data)
            for thumbnail_id, data in rows
            if is_owner(data, owner_uid)
        ]

    def _active_version(self, data: dict[str, Any]) -> dict[str, Any] | None:
        active_id = data.get("activeVersionId")
        for version in data.get("versions") or []:
            if version.get("versionId") == active_id:
                return version
        return None

    def _preview_url(self, data: dict[str, Any]) -> str | None:
        if data.get("status") != ThumbnailStatus.ready.value:
            return None
        version = self._active_version(data)
        path = version.get("storagePath") if version else None
        if not path:
            return None
        try:
            return self.storage.signed_download_url(
                str(path), expires_seconds=self.url_ttl_seconds
            )
        except Exception:  # noqa: BLE001 - a signing hiccup must not hide the concept
            return None

    def _require_owned(
        self, *, owner_uid: str, project_id: str, thumbnail_id: str
    ) -> dict[str, Any]:
        self.projects.get(owner_uid=owner_uid, project_id=project_id)
        data = self.client.get_document(
            thumbnail_concept_path(owner_uid, project_id, thumbnail_id)
        )
        if data is None or not is_owner(data, owner_uid):
            raise NotFoundError(
                "Thumbnail concept not found",
                details={"thumbnailId": thumbnail_id},
            )
        return data
