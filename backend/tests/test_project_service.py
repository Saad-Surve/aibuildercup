from datetime import UTC, datetime, timedelta

import pytest

from app.errors import BadRequestError, NotFoundError
from app.schemas.projects import CreateProject, ProjectStatus, UpdateProject
from app.services.project_service import (
    ProjectService,
    decode_page_token,
    encode_page_token,
    is_owner,
)
from tests.fakes import FakeFirestoreClient, FakeStorageClient

UID = "uid-1"


def make_service() -> tuple[ProjectService, FakeFirestoreClient]:
    client = FakeFirestoreClient()
    return ProjectService(client), client


def test_create_returns_project_and_persists_document() -> None:
    service, client = make_service()
    project = service.create(
        owner_uid=UID,
        payload=CreateProject(name="My video", targetLanguages=["hi"]),
    )

    assert project.name == "My video"
    assert project.status == ProjectStatus.draft
    assert project.targetLanguages == ["hi"]
    stored = client.docs[f"users/{UID}/projects/{project.projectId}"]
    assert stored["ownerUid"] == UID
    assert stored["archivedAt"] is None
    assert stored["status"] == "draft"


def test_get_missing_project_raises_not_found() -> None:
    service, _ = make_service()
    with pytest.raises(NotFoundError):
        service.get(owner_uid=UID, project_id="nope")


def test_get_rejects_document_owned_by_someone_else() -> None:
    service, client = make_service()
    client.set_document(
        f"users/{UID}/projects/p1",
        {
            "ownerUid": "someone-else",
            "name": "x",
            "createdAt": datetime.now(UTC),
            "updatedAt": datetime.now(UTC),
            "archivedAt": None,
        },
    )
    with pytest.raises(NotFoundError):
        service.get(owner_uid=UID, project_id="p1")


def test_update_applies_patch_and_bumps_updated_at() -> None:
    service, _ = make_service()
    created = service.create(owner_uid=UID, payload=CreateProject(name="Old"))
    updated = service.update(
        owner_uid=UID,
        project_id=created.projectId,
        patch=UpdateProject(name="New", description="desc"),
    )
    assert updated.name == "New"
    assert updated.description == "desc"
    assert updated.updatedAt >= created.updatedAt


def test_delete_removes_firestore_tree_and_storage_objects() -> None:
    client = FakeFirestoreClient()
    storage = FakeStorageClient()
    service = ProjectService(client, storage=storage)
    project = service.create(owner_uid=UID, payload=CreateProject(name="Gone"))
    base = f"users/{UID}/projects/{project.projectId}"

    # Everything a project owns: subcollections (incl. nested segments) + GCS objects.
    client.set_document(f"{base}/assets/a1", {"ownerUid": UID})
    client.set_document(f"{base}/jobs/j1", {"ownerUid": UID})
    client.set_document(f"{base}/transcripts/t1", {"ownerUid": UID})
    client.set_document(f"{base}/transcripts/t1/segments/seg-1", {"ownerUid": UID})
    storage.objects[f"{base}/source/a1.mp4"] = "bytes"
    storage.objects[f"{base}/transcripts/v1.json"] = "{}"
    storage.objects[f"{base}/captions/en.vtt"] = "WEBVTT"
    storage.objects[f"{base}/captions/en.srt"] = "1"

    service.delete(owner_uid=UID, project_id=project.projectId)

    assert not any(key == base or key.startswith(base + "/") for key in client.docs)
    assert storage.objects == {}
    items, _ = service.list(owner_uid=UID, limit=20, offset=0)
    assert items == []
    with pytest.raises(NotFoundError):
        service.get(owner_uid=UID, project_id=project.projectId)


def test_delete_rejects_other_owner() -> None:
    client = FakeFirestoreClient()
    service = ProjectService(client, storage=FakeStorageClient())
    project = service.create(owner_uid="other", payload=CreateProject(name="theirs"))
    with pytest.raises(NotFoundError):
        service.delete(owner_uid=UID, project_id=project.projectId)


def test_delete_removes_legacy_archived_project() -> None:
    client = FakeFirestoreClient()
    service = ProjectService(client, storage=FakeStorageClient())
    project = service.create(owner_uid=UID, payload=CreateProject(name="Old"))
    client.update_document(
        f"users/{UID}/projects/{project.projectId}",
        {"status": "archived", "archivedAt": datetime.now(UTC)},
    )
    service.delete(owner_uid=UID, project_id=project.projectId)
    assert f"users/{UID}/projects/{project.projectId}" not in client.docs


def test_list_orders_by_updated_at_desc_and_paginates() -> None:
    service, client = make_service()
    now = datetime.now(UTC)
    for index in range(3):
        client.set_document(
            f"users/{UID}/projects/p{index}",
            {
                "ownerUid": UID,
                "name": f"p{index}",
                "createdAt": now,
                "updatedAt": now + timedelta(minutes=index),
                "archivedAt": None,
            },
        )

    items, has_more = service.list(owner_uid=UID, limit=2, offset=0)
    assert [p.name for p in items] == ["p2", "p1"]
    assert has_more is True

    page2, has_more2 = service.list(owner_uid=UID, limit=2, offset=2)
    assert [p.name for p in page2] == ["p0"]
    assert has_more2 is False


def test_list_isolates_owners() -> None:
    service, _ = make_service()
    service.create(owner_uid=UID, payload=CreateProject(name="mine"))
    service.create(owner_uid="other", payload=CreateProject(name="theirs"))
    items, _ = service.list(owner_uid=UID, limit=20, offset=0)
    assert [p.name for p in items] == ["mine"]


def test_page_token_round_trip() -> None:
    assert decode_page_token(None) == 0
    assert decode_page_token(encode_page_token(40)) == 40


def test_decode_invalid_page_token_raises() -> None:
    with pytest.raises(BadRequestError):
        decode_page_token("not-base64!!")


def test_is_owner() -> None:
    assert is_owner({"ownerUid": "u"}, "u") is True
    assert is_owner({"ownerUid": "u"}, "v") is False
    assert is_owner({}, "u") is False
