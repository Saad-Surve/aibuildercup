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
from app.schemas.projects import (
    CreateProject,
    Project,
    ProjectProgress,
    ProjectStatus,
    UpdateProject,
)
from app.services.firestore_service import (
    FirestoreClient,
    project_path,
    projects_collection_path,
)


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
        primaryLanguage=data.get("primaryLanguage", "en"),
        targetLanguages=data.get("targetLanguages", []),
        targetPlatforms=data.get("targetPlatforms", []),
        isDemo=data.get("isDemo", False),
        demoProfileId=data.get("demoProfileId"),
        status=ProjectStatus(data.get("status", ProjectStatus.draft.value)),
        progress=ProjectProgress(**data["progress"])
        if data.get("progress")
        else None,
        createdAt=data["createdAt"],
        updatedAt=data["updatedAt"],
    )


class ProjectService:
    def __init__(self, client: FirestoreClient) -> None:
        self.client = client

    def create(self, *, owner_uid: str, payload: CreateProject) -> Project:
        project_id = uuid4().hex
        now = datetime.now(UTC)
        document: dict[str, Any] = {
            "ownerUid": owner_uid,
            "name": payload.name,
            "description": payload.description,
            "status": ProjectStatus.draft.value,
            "visibility": "private",
            "sourceAssetId": None,
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

    def update(
        self, *, owner_uid: str, project_id: str, patch: UpdateProject
    ) -> Project:
        data = self._require_owned(owner_uid=owner_uid, project_id=project_id)
        changes = patch.model_dump(exclude_none=True)
        if changes:
            changes["updatedAt"] = datetime.now(UTC)
            self.client.update_document(project_path(owner_uid, project_id), changes)
            data.update(changes)
        return _to_project(project_id, data)

    def mark_processing(
        self, *, owner_uid: str, project_id: str, source_asset_id: str
    ) -> None:
        """Record that a source asset was uploaded and the pipeline is starting."""
        self._require_owned(owner_uid=owner_uid, project_id=project_id)
        now = datetime.now(UTC)
        self.client.update_document(
            project_path(owner_uid, project_id),
            {
                "status": ProjectStatus.processing.value,
                "sourceAssetId": source_asset_id,
                "progress": {
                    "stage": "transcription",
                    "percent": 0,
                    "message": "Queued for transcription",
                },
                "updatedAt": now,
            },
        )

    def soft_delete(self, *, owner_uid: str, project_id: str) -> None:
        self._require_owned(owner_uid=owner_uid, project_id=project_id)
        now = datetime.now(UTC)
        self.client.update_document(
            project_path(owner_uid, project_id),
            {
                "status": ProjectStatus.archived.value,
                "archivedAt": now,
                "updatedAt": now,
            },
        )

    def _require_owned(self, *, owner_uid: str, project_id: str) -> dict[str, Any]:
        data = self.client.get_document(project_path(owner_uid, project_id))
        if data is None or not is_owner(data, owner_uid) or data.get("archivedAt") is not None:
            raise NotFoundError("Project not found", details={"projectId": project_id})
        return data
