from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.dependencies import (
    AuthenticatedUser,
    current_user,
    get_asset_service,
    get_job_service,
)
from app.main import app
from app.schemas.projects import CreateProject
from app.services.asset_service import AssetService
from app.services.job_service import JobService
from app.services.project_service import ProjectService
from tests.fakes import FakeFirestoreClient, FakeStorageClient

UID = "uid-1"


class Ctx:
    def __init__(self, settings: Settings | None = None) -> None:
        self.client = FakeFirestoreClient()
        self.storage = FakeStorageClient()
        self.projects = ProjectService(self.client)
        self.jobs = JobService(self.client)
        self.service = AssetService(
            self.client,
            projects=self.projects,
            jobs=self.jobs,
            storage=self.storage,
            settings=settings or Settings(),
        )

    def new_project(self) -> str:
        return self.projects.create(
            owner_uid=UID, payload=CreateProject(name="P")
        ).projectId


def build_client(context: Ctx) -> TestClient:
    app.dependency_overrides[current_user] = lambda: AuthenticatedUser(
        uid=UID, email="a@b.c"
    )
    app.dependency_overrides[get_asset_service] = lambda: context.service
    app.dependency_overrides[get_job_service] = lambda: context.jobs
    return TestClient(app)


@pytest.fixture
def ctx() -> Iterator[Ctx]:
    context = Ctx()
    build_client(context)
    yield context
    app.dependency_overrides.clear()


def test_upload_session_to_job_flow(ctx: Ctx) -> None:
    project_id = ctx.new_project()
    client = TestClient(app)

    created = client.post(
        f"/api/projects/{project_id}/upload-session",
        json={
            "fileName": "career.mp4",
            "contentType": "video/mp4",
            "sizeBytes": 1024,
        },
    )
    assert created.status_code == 201
    session = created.json()
    assert session["storagePath"].endswith(".mp4")

    # Completing before the object exists is rejected.
    too_early = client.post(
        f"/api/projects/{project_id}/assets/{session['assetId']}/complete"
    )
    assert too_early.status_code == 400
    assert too_early.json()["error"]["code"] == "UPLOAD_NOT_FOUND"

    ctx.storage.objects[session["storagePath"]] = "bytes"
    completed = client.post(
        f"/api/projects/{project_id}/assets/{session['assetId']}/complete"
    )
    assert completed.status_code == 202
    job_id = completed.json()["jobId"]
    assert completed.json()["status"] == "queued"

    job = client.get(f"/api/jobs/{job_id}")
    assert job.status_code == 200
    assert job.json()["type"] == "transcribe"

    assets = client.get(f"/api/projects/{project_id}/assets")
    assert assets.status_code == 200
    items = assets.json()["items"]
    assert len(items) == 1
    assert items[0]["status"] == "uploaded"


def test_upload_session_rejects_bad_content_type(ctx: Ctx) -> None:
    project_id = ctx.new_project()
    response = TestClient(app).post(
        f"/api/projects/{project_id}/upload-session",
        json={"fileName": "x.pdf", "contentType": "application/pdf", "sizeBytes": 10},
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "UNSUPPORTED_MEDIA_TYPE"


def test_upload_session_rejects_oversize() -> None:
    context = Ctx(Settings(max_upload_size_bytes=10))
    build_client(context)
    try:
        project_id = context.new_project()
        response = TestClient(app).post(
            f"/api/projects/{project_id}/upload-session",
            json={
                "fileName": "big.mp4",
                "contentType": "video/mp4",
                "sizeBytes": 11,
            },
        )
        assert response.status_code == 400
        assert response.json()["error"]["code"] == "FILE_TOO_LARGE"
    finally:
        app.dependency_overrides.clear()


def test_complete_unknown_asset_returns_not_found(ctx: Ctx) -> None:
    project_id = ctx.new_project()
    response = TestClient(app).post(
        f"/api/projects/{project_id}/assets/missing/complete"
    )
    assert response.status_code == 404


def test_upload_session_requires_token() -> None:
    app.dependency_overrides.clear()
    response = TestClient(app).post(
        "/api/projects/p1/upload-session",
        json={"fileName": "x.mp4", "contentType": "video/mp4", "sizeBytes": 1},
    )
    assert response.status_code == 401
