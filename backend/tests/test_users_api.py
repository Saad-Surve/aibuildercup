from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app.dependencies import (
    AuthenticatedUser,
    current_user,
    get_identity_deleter,
    get_user_service,
)
from app.main import app
from app.services.user_service import UserService
from tests.fakes import FakeFirestoreClient


@pytest.fixture
def ctx() -> Iterator[tuple[TestClient, FakeFirestoreClient, list[str]]]:
    store = FakeFirestoreClient()
    users = UserService(store)
    deleted: list[str] = []

    app.dependency_overrides[current_user] = lambda: AuthenticatedUser(
        uid="uid-1", email="p@example.com", display_name="Priya"
    )
    app.dependency_overrides[get_user_service] = lambda: users
    app.dependency_overrides[get_identity_deleter] = lambda: (
        lambda uid: deleted.append(uid)
    )

    yield TestClient(app), store, deleted
    app.dependency_overrides.clear()


def test_get_me_creates_user(
    ctx: tuple[TestClient, FakeFirestoreClient, list[str]],
) -> None:
    client, store, _ = ctx
    response = client.get("/me")
    assert response.status_code == 200
    assert response.json()["uid"] == "uid-1"
    assert "users/uid-1" in store.docs


def test_delete_me_removes_data_and_identity(
    ctx: tuple[TestClient, FakeFirestoreClient, list[str]],
) -> None:
    client, store, deleted = ctx
    client.get("/me")
    store.set_document(
        "users/uid-1/projects/p1", {"ownerUid": "uid-1", "name": "x"}
    )
    store.set_document("users/other", {"uid": "other"})

    response = client.delete("/me")

    assert response.status_code == 204
    assert [key for key in store.docs if key.startswith("users/uid-1")] == []
    assert "users/other" in store.docs
    assert deleted == ["uid-1"]


def test_delete_me_requires_auth() -> None:
    app.dependency_overrides.clear()
    response = TestClient(app).delete("/me")
    assert response.status_code == 401
