"""Project persistence and ownership checks.

Every read and write is scoped to the caller's `ownerUid`, and the stored document is checked
against `ownerUid` again before it is returned (defense in depth). The service depends on the
narrow `FirestoreClient` protocol so it can be tested without Firestore.
"""

import base64
import binascii
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from app.errors import BadRequestError, NotFoundError
from app.realtime.events import emit_project
from app.schemas.draft import DraftSummary
from app.schemas.projects import (
    CreateProject,
    Project,
    ProjectKind,
    ProjectProgress,
    ProjectStatus,
    UpdateProject,
)
from app.services.firestore_service import (
    FirestoreClient,
    project_object_prefix,
    project_path,
    projects_collection_path,
)
from app.services.storage_service import StorageClient


def is_owner(document: dict[str, Any], owner_uid: str) -> bool:
    return document.get("ownerUid") == owner_uid


def encode_page_token(offset: int) -> str:
    return base64.urlsafe_b64encode(str(offset).encode()).decode()


def decode_page_token(token: str | None) -> int:
    if token is None or token == "":
        return 0
    try:
        offset = int(base64.urlsafe_b64decode(token.encode()).decode())
    except (binascii.Error, ValueError, UnicodeDecodeError) as exc:
        raise BadRequestError("Invalid pageToken") from exc
    if offset < 0:
        raise BadRequestError("Invalid pageToken")
    return offset


def _to_project(project_id: str, data: dict[str, Any]) -> Project:
    return Project(
        projectId=project_id,
        name=data.get("name", ""),
        description=data.get("description", ""),
        thumbnailConcept=data.get("thumbnailConcept", ""),
        primaryLanguage=data.get("primaryLanguage", "en"),
        targetLanguages=data.get("targetLanguages", []),
        targetPlatforms=data.get("targetPlatforms", []),
        isDemo=data.get("isDemo", False),
        demoProfileId=data.get("demoProfileId"),
        kind=ProjectKind(data.get("kind", ProjectKind.video.value)),
        draftFormat=data.get("draftFormat", "written"),
        draftSummary=DraftSummary(**data["draftSummary"])
        if data.get("draftSummary")
        else None,
        sourceDraftId=data.get("sourceDraftId"),
        sourceDraftName=data.get("sourceDraftName"),
        status=ProjectStatus(data.get("status", ProjectStatus.draft.value)),
        progress=ProjectProgress(**data["progress"])
        if data.get("progress")
        else None,
        sourceAssetId=data.get("sourceAssetId"),
        sourceRevision=data.get("sourceRevision"),
        revisionCount=int(data.get("sourceRevisionCounter", 0) or 0),
        posterStoragePath=data.get("posterStoragePath"),
        createdAt=data["createdAt"],
        updatedAt=data["updatedAt"],
    )


class ProjectService:
    def __init__(
        self,
        client: FirestoreClient,
        *,
        storage: StorageClient | None = None,
        url_ttl_seconds: int = 900,
    ) -> None:
        self.client = client
        self.storage = storage
        self.url_ttl_seconds = url_ttl_seconds

    def poster_url(self, project: Project) -> str | None:
        """Signed URL for the applied thumbnail cover, or None.

        Minted at the API boundary rather than inside `get`/`list`, because those are also
        called for ownership checks on hot paths (thumbnail polling, uploads) and signing
        is a network round-trip.
        """
        if not project.posterStoragePath or self.storage is None:
            return None
        try:
            return self.storage.signed_download_url(
                project.posterStoragePath, expires_seconds=self.url_ttl_seconds
            )
        except Exception:  # noqa: BLE001 - a signing hiccup must not hide the project
            return None

    def _require_draft_source(self, *, owner_uid: str, draft_id: str) -> dict[str, Any]:
        """Validate a script-source link: owned, live, and actually a draft."""
        draft = self._require_owned(owner_uid=owner_uid, project_id=draft_id)
        if draft.get("kind") != ProjectKind.draft.value:
            raise BadRequestError(
                "Only a draft project can be a script source.",
                code="PROJECT_NOT_A_DRAFT",
                details={"projectId": draft_id},
            )
        return draft

    def create(self, *, owner_uid: str, payload: CreateProject) -> Project:
        project_id = uuid4().hex
        now = datetime.now(UTC)
        source_name: str | None = None
        if payload.sourceDraftId is not None:
            if payload.kind != ProjectKind.video:
                raise BadRequestError(
                    "Only a video project can link a script source.",
                    code="PROJECT_LINK_WRONG_KIND",
                    details={"kind": payload.kind.value},
                )
            source_name = str(
                self._require_draft_source(
                    owner_uid=owner_uid, draft_id=payload.sourceDraftId
                ).get("name", "")
                or ""
            )
        document: dict[str, Any] = {
            "ownerUid": owner_uid,
            "name": payload.name,
            "description": payload.description,
            "thumbnailConcept": payload.thumbnailConcept,
            "kind": payload.kind.value,
            "draftFormat": payload.draftFormat.value,
            "draftSummary": None,
            "sourceDraftId": payload.sourceDraftId,
            "sourceDraftName": source_name,
            "status": ProjectStatus.draft.value,
            "visibility": "private",
            "sourceAssetId": None,
            "sourceRevision": None,
            "sourceRevisionCounter": 0,
            "activeTranscriptId": None,
            "activeAnalysisRunId": None,
            "personaVersionUsed": None,
            "primaryLanguage": payload.primaryLanguage,
            "targetLanguages": payload.targetLanguages,
            "targetPlatforms": payload.targetPlatforms,
            "progress": {"stage": "draft", "percent": 0, "message": ""},
            "summary": None,
            "isDemo": payload.isDemo,
            "demoProfileId": payload.demoProfileId,
            "createdAt": now,
            "updatedAt": now,
            "archivedAt": None,
        }
        self.client.set_document(project_path(owner_uid, project_id), document)
        return _to_project(project_id, document)

    def list(self, *, owner_uid: str, limit: int, offset: int) -> tuple[list[Project], bool]:
        rows = self.client.query_collection(
            projects_collection_path(owner_uid),
            filters=[("ownerUid", "==", owner_uid)],
            order_by=[("updatedAt", "DESCENDING")],
            limit=limit + 1,
            offset=offset,
        )
        active = [(pid, data) for pid, data in rows if data.get("archivedAt") is None]
        has_more = len(active) > limit
        page = active[:limit]
        return [_to_project(pid, data) for pid, data in page], has_more

    def get(self, *, owner_uid: str, project_id: str) -> Project:
        data = self._require_owned(owner_uid=owner_uid, project_id=project_id)
        return _to_project(project_id, data)

    def update(self, *, owner_uid: str, project_id: str, patch: UpdateProject) -> Project:
        data = self._require_owned(owner_uid=owner_uid, project_id=project_id)
        changes = patch.model_dump(exclude_none=True)
        if "sourceDraftId" in patch.model_fields_set:
            # Explicit null clears the link; omitted leaves it untouched
            # (exclude_none would otherwise swallow the null).
            if patch.sourceDraftId is None:
                changes["sourceDraftId"] = None
                changes["sourceDraftName"] = None
            else:
                if data.get("kind") != ProjectKind.video.value:
                    raise BadRequestError(
                        "Only a video project can link a script source.",
                        code="PROJECT_LINK_WRONG_KIND",
                        details={"projectId": project_id},
                    )
                if patch.sourceDraftId == project_id:
                    raise BadRequestError(
                        "A project cannot be its own script source.",
                        code="PROJECT_LINK_SELF",
                        details={"projectId": project_id},
                    )
                draft = self._require_draft_source(
                    owner_uid=owner_uid, draft_id=patch.sourceDraftId
                )
                changes["sourceDraftId"] = patch.sourceDraftId
                changes["sourceDraftName"] = str(draft.get("name", "") or "")
        if changes:
            changes["updatedAt"] = datetime.now(UTC)
            self.client.update_document(project_path(owner_uid, project_id), changes)
            data.update(changes)
        return _to_project(project_id, data)

    def mark_processing(
        self,
        *,
        owner_uid: str,
        project_id: str,
        source_asset_id: str,
        revision: int | None = None,
    ) -> None:
        """Record that a source asset was uploaded and the pipeline is starting.

        `revision` is the revision number of the uploaded source, when known. The project
        points at it as the active source; the revision counter only ever moves forward, so
        re-completing an older upload cannot lower the project's revision count.
        """
        raw = self._require_owned(owner_uid=owner_uid, project_id=project_id)
        now = datetime.now(UTC)
        changes: dict[str, Any] = {
            "status": ProjectStatus.processing.value,
            "sourceAssetId": source_asset_id,
            "progress": {
                "stage": "transcription",
                "percent": 0,
                "message": "Queued for transcription",
            },
            "updatedAt": now,
        }
        if revision is not None:
            counter = int(raw.get("sourceRevisionCounter", 0) or 0)
            changes["sourceRevision"] = revision
            if revision > counter:
                changes["sourceRevisionCounter"] = revision
        self.client.update_document(project_path(owner_uid, project_id), changes)
        emit_project(
            owner_uid,
            project_id,
            status=ProjectStatus.processing,
            stage="transcription",
            percent=0,
            message="Queued for transcription",
        )

    def mark_transcript_ready(
        self,
        *,
        owner_uid: str,
        project_id: str,
        transcript_id: str,
        duration_ms: int,
        word_count: int,
    ) -> None:
        """Flip a processing project to ready once its transcript lands."""
        self._require_owned(owner_uid=owner_uid, project_id=project_id)
        now = datetime.now(UTC)
        self.client.update_document(
            project_path(owner_uid, project_id),
            {
                "status": ProjectStatus.ready.value,
                "activeTranscriptId": transcript_id,
                "progress": {
                    "stage": "ready",
                    "percent": 100,
                    "message": "Transcript ready",
                },
                "summary": {
                    "durationMs": duration_ms,
                    "transcriptWordCount": word_count,
                },
                "updatedAt": now,
            },
        )
        emit_project(
            owner_uid,
            project_id,
            status=ProjectStatus.ready,
            stage="ready",
            percent=100,
            message="Transcript ready",
        )

    def update_draft_summary(
        self,
        *,
        owner_uid: str,
        project_id: str,
        summary: DraftSummary,
        status: ProjectStatus | None = None,
    ) -> None:
        """Keep the project's denormalised draft summary (and status) in sync."""
        self._require_owned(owner_uid=owner_uid, project_id=project_id)
        now = datetime.now(UTC)
        changes: dict[str, Any] = {
            "draftSummary": summary.model_dump(),
            "updatedAt": now,
        }
        if status is not None:
            changes["status"] = status.value
            changes["progress"] = {
                "stage": "draft",
                "percent": 100 if status == ProjectStatus.ready else 0,
                "message": "Draft ready" if status == ProjectStatus.ready else "Writing",
            }
        self.client.update_document(project_path(owner_uid, project_id), changes)
        emit_project(
            owner_uid,
            project_id,
            status=status or ProjectStatus.draft,
            stage="draft",
            percent=100 if status == ProjectStatus.ready else 0,
            message="Draft updated",
        )

    def mark_failed(self, *, owner_uid: str, project_id: str, message: str) -> None:
        self._require_owned(owner_uid=owner_uid, project_id=project_id)
        now = datetime.now(UTC)
        self.client.update_document(
            project_path(owner_uid, project_id),
            {
                "status": ProjectStatus.failed.value,
                "progress": {"stage": "failed", "percent": 0, "message": message},
                "updatedAt": now,
            },
        )
        emit_project(
            owner_uid,
            project_id,
            status=ProjectStatus.failed,
            stage="failed",
            percent=0,
            message=message,
        )

    def delete(self, *, owner_uid: str, project_id: str) -> None:
        """Permanently delete a project and everything it owns.

        Removes every Cloud Storage object under the project prefix (source video, canonical
        transcript JSON, VTT/SRT captions, and any future derived media) and the whole Firestore
        subtree (assets, jobs, transcripts + segments). Already-archived projects are still
        deletable so legacy soft-deleted documents can be cleaned up.
        """
        data = self.client.get_document(project_path(owner_uid, project_id))
        if data is None or not is_owner(data, owner_uid):
            raise NotFoundError("Project not found", details={"projectId": project_id})
        if self.storage is None:
            raise RuntimeError("ProjectService.delete requires a storage client.")
        self.storage.delete_prefix(project_object_prefix(owner_uid, project_id))
        self.client.delete_document_tree(project_path(owner_uid, project_id))

    def _require_owned(self, *, owner_uid: str, project_id: str) -> dict[str, Any]:
        data = self.client.get_document(project_path(owner_uid, project_id))
        if data is None or not is_owner(data, owner_uid) or data.get("archivedAt") is not None:
            raise NotFoundError("Project not found", details={"projectId": project_id})
        return data
