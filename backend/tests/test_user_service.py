from app.schemas.onboarding import OnboardingStatus, OnboardingStep
from app.services.user_service import UserService
from tests.fakes import FakeFirestoreClient, FakeStorageClient

UID = "uid-1"


def make_service() -> tuple[UserService, FakeFirestoreClient]:
    client = FakeFirestoreClient()
    return UserService(client), client


def test_ensure_user_creates_defaults() -> None:
    service, client = make_service()
    data = service.ensure_user(UID, display_name="Priya", email="p@example.com")

    assert data["displayName"] == "Priya"
    assert data["onboarding"]["status"] == "not_started"
    assert data["persona"] is None
    assert f"users/{UID}" in client.docs


def test_ensure_user_is_idempotent_and_refreshes_profile() -> None:
    service, client = make_service()
    service.ensure_user(UID, display_name="Priya", email="p@example.com")
    service.ensure_user(UID, display_name="Priya Sharma", email="p@example.com")

    assert len(client.docs) == 1
    assert client.docs[f"users/{UID}"]["displayName"] == "Priya Sharma"


def test_save_onboarding_step_merges_answers() -> None:
    service, _ = make_service()
    service.save_onboarding_step(
        UID, OnboardingStep(step="creator_profile", answers={"creatorName": "Priya"})
    )
    state = service.save_onboarding_step(
        UID, OnboardingStep(step="platforms", answers={"platforms": ["youtube"]})
    )

    assert state.status == OnboardingStatus.in_progress
    assert state.currentStep == "platforms"
    assert state.answers == {"creatorName": "Priya", "platforms": ["youtube"]}


def test_mark_onboarding_complete_does_not_regress_on_edit() -> None:
    service, _ = make_service()
    service.mark_onboarding_complete(UID)
    state = service.save_onboarding_step(
        UID, OnboardingStep(step="edit", answers={"x": 1})
    )
    assert state.status == OnboardingStatus.completed


def test_to_me_reflects_onboarding_and_persona() -> None:
    service, _ = make_service()
    service.mark_onboarding_complete(UID)
    service.set_persona(
        UID,
        storage_path=f"users/{UID}/profile/persona.md",
        version=2,
        language="hi",
        approved_at=service.get_user(UID)["updatedAt"],
    )
    me = service.to_me(UID, service.get_user(UID))

    assert me.uid == UID
    assert me.onboardingCompleted is True
    assert me.personaVersion == 2
    assert me.preferences.defaultLanguage == "en"


def test_delete_account_removes_firestore_and_storage() -> None:
    client = FakeFirestoreClient()
    storage = FakeStorageClient()
    # A full project subtree, not just the user document.
    owned_docs = [
        f"users/{UID}",
        f"users/{UID}/projects/p1",
        f"users/{UID}/projects/p1/assets/a1",
        f"users/{UID}/projects/p1/jobs/j1",
        f"users/{UID}/personaRevisions/r1",
    ]
    for path in owned_docs:
        client.set_document(path, {"ownerUid": UID})
    client.set_document("users/other", {"uid": "other"})
    client.set_document("users/other/projects/p1", {"ownerUid": "other"})

    owned_objects = [
        f"users/{UID}/profile/persona.md",
        f"users/{UID}/profile/revisions/persona-v1.md",
        f"users/{UID}/projects/p1/source/a1.mp4",
    ]
    for path in owned_objects:
        storage.upload_text(path, "x")
    storage.upload_text("users/other/projects/p1/source/a1.mp4", "other")

    UserService(client, storage=storage).delete_account(UID)

    assert [path for path in client.docs if path.startswith(f"users/{UID}")] == []
    assert client.docs["users/other"]["uid"] == "other"
    assert "users/other/projects/p1" in client.docs
    assert list(storage.objects) == ["users/other/projects/p1/source/a1.mp4"]


def test_delete_account_without_storage_still_clears_firestore() -> None:
    client = FakeFirestoreClient()
    client.set_document(f"users/{UID}", {"uid": UID})

    UserService(client).delete_account(UID)

    assert f"users/{UID}" not in client.docs
