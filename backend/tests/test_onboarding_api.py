from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.dependencies import (
    AuthenticatedUser,
    current_user,
    get_persona_service,
    get_user_service,
)
from app.main import app
from app.services.persona_service import PersonaService
from app.services.user_service import UserService
from tests.fakes import FakeFirestoreClient, FakeStorageClient, StubLlmProvider


@pytest.fixture
def client(tmp_path) -> Iterator[TestClient]:
    store = FakeFirestoreClient()
    users = UserService(store)
    persona = PersonaService(
        client=store,
        storage=FakeStorageClient(),
        llm=StubLlmProvider(),
        users=users,
        settings=Settings(mock_mode="on", cassette_dir=str(tmp_path)),
    )
    app.dependency_overrides[current_user] = lambda: AuthenticatedUser(
        uid="uid-1", email="p@example.com", display_name="Priya"
    )
    app.dependency_overrides[get_user_service] = lambda: users
    app.dependency_overrides[get_persona_service] = lambda: persona
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_get_me_creates_profile(client: TestClient) -> None:
    response = client.get("/api/me")
    assert response.status_code == 200
    body = response.json()
    assert body["uid"] == "uid-1"
    assert body["displayName"] == "Priya"
    assert body["onboardingCompleted"] is False
    assert body["personaVersion"] is None


def test_onboarding_flow_through_persona(client: TestClient) -> None:
    saved = client.put(
        "/api/onboarding",
        json={
            "step": "creator_profile",
            "answers": {"creatorName": "Priya", "topics": ["finance"]},
        },
    )
    assert saved.status_code == 200
    assert saved.json()["status"] == "in_progress"
    assert saved.json()["answers"]["topics"] == ["finance"]

    state = client.get("/api/onboarding").json()
    assert state["currentStep"] == "creator_profile"

    complete = client.post("/api/onboarding/complete")
    assert complete.status_code == 200
    ref = complete.json()
    assert ref["onboardingCompleted"] is True
    assert ref["personaVersion"] == 1

    me = client.get("/api/me").json()
    assert me["onboardingCompleted"] is True
    assert me["personaVersion"] == 1


def test_get_persona_before_completion_is_not_found(client: TestClient) -> None:
    response = client.get("/api/persona")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "PERSONA_NOT_FOUND"


def test_patch_persona_bumps_version(client: TestClient) -> None:
    client.post("/api/onboarding/complete")
    response = client.patch(
        "/api/persona", json={"content": "# Edited\n", "expectedVersion": 1}
    )
    assert response.status_code == 200
    assert response.json()["version"] == 2
    assert response.json()["content"] == "# Edited\n"


def test_patch_persona_conflict(client: TestClient) -> None:
    client.post("/api/onboarding/complete")
    response = client.patch(
        "/api/persona", json={"content": "# Stale\n", "expectedVersion": 5}
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "PERSONA_VERSION_CONFLICT"


def test_onboarding_step_requires_step(client: TestClient) -> None:
    response = client.put("/api/onboarding", json={"answers": {}})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"
