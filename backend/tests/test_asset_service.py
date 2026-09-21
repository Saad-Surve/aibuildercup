from datetime import UTC, datetime

import pytest

from app.config import Settings
from app.errors import BadRequestError, NotFoundError
from app.schemas.assets import AssetStatus, CreateUploadSession, UploadSession
from app.schemas.projects import CreateProject
from app.services.asset_service import AssetService
from app.services.job_service import JobService
from app.services.project_service import ProjectService
from tests.fakes import FakeFirestoreClient, FakeStorageClient

UID = "uid-1"


class Harness:
    def __init__(self, settings: Settings | None = None) -> None:
        self.client = FakeFirestoreClient()
        self.projects = ProjectService(self.client)
        self.jobs = JobService(self.client)
        self.storage = FakeStorageClient()
        self.service = AssetService(
            self.client,
            projects=self.projects,
            jobs=self.jobs,
            storage=self.storage,
            settings=settings or Settings(),
        )

    def project(self, name: str = "P") -> str:
        return self.projects.create(
            owner_uid=UID, payload=CreateProject(name=name)
        ).projectId


def upload(harness: Harness, project_id: str, **overrides: object) -> UploadSession:
    payload = {
        "fileName": "career.mp4",
        "contentType": "video/mp4",
        "sizeBytes": 1024,
        **overrides,
    }
    return harness.service.create_upload_session(
        owner_uid=UID, project_id=project_id, payload=CreateUploadSession(**payload)
    )


def test_create_upload_session_persists_pending_asset() -> None:
    h = Harness()
    project_id = h.project()
    session = upload(h, project_id)

    assert session.storagePath == f"users/{UID}/projects/{project_id}/source/{session.assetId}.mp4"
    assert session.uploadUrl.startswith("https://storage.example/upload/")
    assert session.requiredHeaders == {"Content-Type": "video/mp4"}

    stored = h.client.docs[f"users/{UID}/projects/{project_id}/assets/{session.assetId}"]
    assert stored["status"] == "pending"
    assert stored["type"] == "source_video"
    assert stored["ownerUid"] == UID


def test_create_upload_session_rejects_unsupported_type() -> None:
    h = Harness()
    project_id = h.project()
    with pytest.raises(BadRequestError) as exc:
        upload(h, project_id, contentType="application/pdf")
    assert exc.value.code == "UNSUPPORTED_MEDIA_TYPE"


def test_create_upload_session_rejects_oversize() -> None:
    h = Harness(Settings(max_upload_size_bytes=100))
    project_id = h.project()
    with pytest.raises(BadRequestError) as exc:
        upload(h, project_id, sizeBytes=101)
    assert exc.value.code == "FILE_TOO_LARGE"


def test_create_upload_session_requires_owned_project() -> None:
    h = Harness()
    with pytest.raises(NotFoundError):
        upload(h, "missing")


def test_complete_requires_object_in_storage() -> None:
    h = Harness()
    project_id = h.project()
    session = upload(h, project_id)
    with pytest.raises(BadRequestError) as exc:
        h.service.complete_upload(
            owner_uid=UID, project_id=project_id, asset_id=session.assetId
        )
    assert exc.value.code == "UPLOAD_NOT_FOUND"


def test_complete_marks_asset_uploaded_and_queues_transcription() -> None:
    h = Harness()
    project_id = h.project()
    session = upload(h, project_id)
    h.storage.objects[session.storagePath] = "bytes"

    job = h.service.complete_upload(
        owner_uid=UID, project_id=project_id, asset_id=session.assetId
    )

    assert job.type.value == "transcribe"
    assert job.status.value == "queued"
    stored = h.client.docs[f"users/{UID}/projects/{project_id}/assets/{session.assetId}"]
    assert stored["status"] == "uploaded"
    project = h.client.docs[f"users/{UID}/projects/{project_id}"]
    assert project["status"] == "processing"
    assert project["sourceAssetId"] == session.assetId


def test_complete_is_idempotent() -> None:
    h = Harness()
    project_id = h.project()
    session = upload(h, project_id)
    h.storage.objects[session.storagePath] = "bytes"

    first = h.service.complete_upload(
        owner_uid=UID, project_id=project_id, asset_id=session.assetId
    )
    second = h.service.complete_upload(
        owner_uid=UID, project_id=project_id, asset_id=session.assetId
    )
    assert first.jobId == second.jobId


def test_list_assets_orders_newest_first_and_isolates_owner() -> None:
    h = Harness()
    project_id = h.project()
    early = upload(h, project_id)
    later = upload(h, project_id)
    # Force distinct timestamps so ordering is deterministic.
    h.client.docs[
        f"users/{UID}/projects/{project_id}/assets/{early.assetId}"
    ]["createdAt"] = datetime(2026, 1, 1, tzinfo=UTC)
    h.client.docs[
        f"users/{UID}/projects/{project_id}/assets/{later.assetId}"
    ]["createdAt"] = datetime(2026, 1, 2, tzinfo=UTC)

    assets = h.service.list(owner_uid=UID, project_id=project_id)
    assert [a.assetId for a in assets] == [later.assetId, early.assetId]
    assert all(a.status == AssetStatus.pending for a in assets)


def test_list_assets_requires_owned_project() -> None:
    h = Harness()
    with pytest.raises(NotFoundError):
        h.service.list(owner_uid=UID, project_id="missing")
