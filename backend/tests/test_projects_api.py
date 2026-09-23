from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app.dependencies import AuthenticatedUser, current_user, get_project_service
from app.main import app
from app.services.project_service import ProjectService
from tests.fakes import FakeFirestoreClient, FakeStorageClient


@pytest.fixture
def client() -> Iterator[TestClient]:
    service = ProjectService(FakeFirestoreClient(), storage=FakeStorageClient())
    app.dependency_overrides[current_user] = lambda: AuthenticatedUser(
        uid="uid-1", email="a@b.c"
    )
    app.dependency_overrides[get_project_service] = lambda: service
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_create_project(client: TestClient) -> None:
    response = client.post("/api/projects", json={"name": "Career Advice"})
    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "Career Advice"
    assert body["status"] == "draft"
    assert body["projectId"]


def test_create_project_requires_name(client: TestClient) -> None:
    response = client.post("/api/projects", json={})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_list_projects(client: TestClient) -> None:
    client.post("/api/projects", json={"name": "One"})
    client.post("/api/projects", json={"name": "Two"})
    response = client.get("/api/projects")
    assert response.status_code == 200
    body = response.json()
    assert len(body["items"]) == 2
    assert body["nextPageToken"] is None


def test_get_project_not_found_envelope(client: TestClient) -> None:
    response = client.get("/api/projects/missing")
    assert response.status_code == 404
    error = response.json()["error"]
    assert error["code"] == "NOT_FOUND"
    assert error["requestId"]


def test_update_project(client: TestClient) -> None:
    project_id = client.post("/api/projects", json={"name": "Old"}).json()["projectId"]
    response = client.patch(f"/api/projects/{project_id}", json={"name": "New"})
    assert response.status_code == 200
    assert response.json()["name"] == "New"


def test_delete_project(client: TestClient) -> None:
    project_id = client.post("/api/projects", json={"name": "Bye"}).json()["projectId"]
    response = client.delete(f"/api/projects/{project_id}")
    assert response.status_code == 202
    assert client.get(f"/api/projects/{project_id}").status_code == 404


def test_missing_token_is_unauthorized() -> None:
    app.dependency_overrides.clear()
    response = TestClient(app).get("/api/projects")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHORIZED"
