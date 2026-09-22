from typing import Any

import pytest

from app.config import Settings
from app.errors import ConflictError, NotFoundError
from app.providers.base import LlmProvider as LlmProviderProtocol
from app.schemas.onboarding import OnboardingStatus, OnboardingStep
from app.services.persona_service import PersonaService, build_persona_markdown
from app.services.user_service import UserService
from tests.fakes import FakeFirestoreClient, FakeStorageClient, StubLlmProvider

UID = "uid-1"


class _FailingLlm:
    """LLM stub that always raises, to exercise the template fallback."""

    async def complete_json(self, **_: Any) -> dict[str, Any]:
        raise RuntimeError("boom")


def make_service(
    *, llm: LlmProviderProtocol | None = None
) -> tuple[PersonaService, FakeFirestoreClient, FakeStorageClient, UserService]:
    client = FakeFirestoreClient()
    storage = FakeStorageClient()
    users = UserService(client)
    service = PersonaService(
        client=client,
        storage=storage,
        llm=llm or StubLlmProvider(),
        users=users,
        settings=Settings(),
    )
    return service, client, storage, users


async def test_complete_onboarding_creates_persona() -> None:
    service, client, storage, users = make_service()
    users.save_onboarding_step(
        UID,
        OnboardingStep(
            step="creator_profile",
            answers={"creatorName": "Priya", "primaryLanguage": "hi"},
        ),
    )

    ref = await service.complete_onboarding(UID)

    assert ref.onboardingCompleted is True
    assert ref.personaVersion == 1
    assert storage.objects[ref.personaStoragePath] == "# Stub persona\n"
    assert users.get_onboarding(UID).status == OnboardingStatus.completed
    assert users.get_user(UID)["persona"]["version"] == 1
    revisions = [path for path in client.docs if "/personaRevisions/" in path]
    assert len(revisions) == 1


async def test_complete_onboarding_falls_back_when_llm_fails() -> None:
    service, _, storage, users = make_service(llm=_FailingLlm())
    users.save_onboarding_step(
        UID, OnboardingStep(step="s", answers={"creatorName": "Priya"})
    )

    ref = await service.complete_onboarding(UID)
    content = storage.objects[ref.personaStoragePath]

    assert "Priya" in content
    assert "## Audience" in content


def test_get_without_persona_raises_not_found() -> None:
    service, *_ = make_service()
    with pytest.raises(NotFoundError):
        service.get(UID)


async def test_get_returns_persona_content() -> None:
    service, *_ = make_service()
    await service.complete_onboarding(UID)
    persona = service.get(UID)
    assert persona.version == 1
    assert persona.content.startswith("# Stub persona")


async def test_update_persona_bumps_version_and_writes_revision() -> None:
    service, client, storage, _ = make_service()
    await service.complete_onboarding(UID)

    updated = service.update(UID, content="# Persona v2\n", expected_version=1)

    assert updated.version == 2
    assert storage.objects[updated.storagePath] == "# Persona v2\n"
    revisions = [path for path in client.docs if "/personaRevisions/" in path]
    assert len(revisions) == 2


async def test_update_persona_version_conflict() -> None:
    service, *_ = make_service()
    await service.complete_onboarding(UID)

    with pytest.raises(ConflictError) as exc:
        service.update(UID, content="# stale\n", expected_version=99)

    assert exc.value.code == "PERSONA_VERSION_CONFLICT"
    assert exc.value.details["currentVersion"] == 1
    assert exc.value.details["expectedVersion"] == 99


def test_build_persona_markdown_includes_answers() -> None:
    markdown = build_persona_markdown(
        {"creatorName": "Priya", "topics": ["finance"], "platforms": ["youtube"]}
    )
    assert "# Creator Persona — Priya" in markdown
    assert "finance" in markdown
    assert "- youtube" in markdown
