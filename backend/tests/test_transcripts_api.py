from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app.dependencies import (
    AuthenticatedUser,
    current_user,
    get_transcript_service,
)
from app.main import app
from app.schemas.projects import CreateProject
from app.services.project_service import ProjectService
from app.services.transcript_service import TranscriptService
from tests.fakes import FakeFirestoreClient, FakeStorageClient

UID = "uid-1"


class Ctx:
    def __init__(self) -> None:
        self.client = FakeFirestoreClient()
        self.storage = FakeStorageClient()
        self.projects = ProjectService(self.client)
        self.service = TranscriptService(self.client, storage=self.storage)

    def new_project(self) -> str:
        return self.projects.create(owner_uid=UID, payload=CreateProject(name="P")).projectId


@pytest.fixture
def ctx() -> Iterator[Ctx]:
    context = Ctx()
    app.dependency_overrides[current_user] = lambda: AuthenticatedUser(uid=UID, email="a@b.c")
    app.dependency_overrides[get_transcript_service] = lambda: context.service
    yield context
    app.dependency_overrides.clear()


def test_get_transcript_returns_segments(ctx: Ctx) -> None:
    project_id = ctx.new_project()
    ctx.service.save(
        owner_uid=UID,
        project_id=project_id,
        source_asset_id="asset-1",
        language="en-US",
        words=[
            {"word": "Hello", "startMs": 0, "endMs": 300},
            {"word": "world.", "startMs": 300, "endMs": 600},
        ],
    )
    response = TestClient(app).get(f"/api/projects/{project_id}/transcript")
    assert response.status_code == 200
    body = response.json()
    assert body["language"] == "en-US"
    assert body["durationMs"] == 600
    assert [s["text"] for s in body["segments"]] == ["Hello world."]
    assert body["segments"][0]["segmentId"] == "seg-1"


def test_get_transcript_before_ready_returns_not_found(ctx: Ctx) -> None:
    project_id = ctx.new_project()
    response = TestClient(app).get(f"/api/projects/{project_id}/transcript")
    assert response.status_code == 404


def test_get_transcript_requires_token(ctx: Ctx) -> None:
    app.dependency_overrides.clear()
    try:
        response = TestClient(app).get("/api/projects/p1/transcript")
        assert response.status_code == 401
    finally:
        app.dependency_overrides[current_user] = lambda: AuthenticatedUser(uid=UID, email="a@b.c")
        app.dependency_overrides[get_transcript_service] = lambda: ctx.service
