"""No API response may ever be cached.

Firebase Hosting serves `/api/**` through its CDN, which cached a 404 from
`GET /transcript` for ten minutes and hid a transcript that already existed —
the workspace cleared its progress card but the transcript never appeared.
The origin has to say `no-store` so no layer in front can second-guess it.
"""

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app.dependencies import AuthenticatedUser, current_user
from app.errors import NotFoundError
from app.main import app

NO_STORE = "no-store, no-cache, must-revalidate"


@pytest.fixture
def client() -> Iterator[TestClient]:
    app.dependency_overrides[current_user] = lambda: AuthenticatedUser(
        uid="uid-1", email="a@b.c"
    )
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_success_responses_are_not_cacheable(client: TestClient) -> None:
    response = client.get("/api/healthz")
    assert response.status_code == 200
    assert response.headers["cache-control"] == NO_STORE
    assert response.headers["vary"] == "Authorization"


def test_error_responses_are_not_cacheable(client: TestClient) -> None:
    """The exact bug: a 404 must not be reused once the resource exists."""
    from app.dependencies import get_transcript_service

    class _MissingTranscript:
        def get(self, **_: object) -> None:
            raise NotFoundError("Transcript not ready", details={"projectId": "p1"})

    app.dependency_overrides[get_transcript_service] = lambda: _MissingTranscript()
    try:
        response = client.get("/api/projects/p1/transcript")
    finally:
        app.dependency_overrides.pop(get_transcript_service, None)

    assert response.status_code == 404
    assert response.headers["cache-control"] == NO_STORE
    assert response.headers["vary"] == "Authorization"
    assert response.json()["error"]["message"] == "Transcript not ready"


def test_validation_errors_are_not_cacheable(client: TestClient) -> None:
    from app.dependencies import get_project_service

    class _BadInput:
        def list(self, **_: object) -> None:
            raise ValueError("unused")

    app.dependency_overrides[get_project_service] = lambda: _BadInput()
    try:
        response = client.get("/api/projects", params={"limit": "not-a-number"})
    finally:
        app.dependency_overrides.pop(get_project_service, None)

    assert response.status_code == 422
    assert response.headers["cache-control"] == NO_STORE


def test_unauthenticated_errors_are_not_cacheable() -> None:
    """No overrides: the 401 from the auth dependency must not be cached either."""
    response = TestClient(app).get("/api/projects")
    assert response.status_code == 401
    assert response.headers["cache-control"] == NO_STORE
