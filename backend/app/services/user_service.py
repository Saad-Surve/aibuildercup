"""User profile and onboarding state.

The user document (`users/{uid}`) is the root of every user-owned path. It is created lazily on
the first authenticated request so the frontend never has to bootstrap it. Onboarding answers are
stored on the same document under `onboarding`.
"""

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from app.schemas.onboarding import OnboardingState, OnboardingStatus, OnboardingStep
from app.schemas.users import AvatarState, Me, Preferences
from app.services.firestore_service import FirestoreClient, user_path
from app.services.paths import user_object_prefix
from app.services.storage_service import StorageClient

if TYPE_CHECKING:
    from app.services.connection_service import ConnectionService

DEFAULT_PREFERENCES: dict[str, Any] = {
    "timezone": "UTC",
    "defaultLanguage": "en",
    "defaultPlatforms": [],
    "notificationsEnabled": True,
}

DEFAULT_LIMITS: dict[str, Any] = {
    "maxVideoDurationMs": 1_800_000,
    "maxVideoSizeBytes": 524_288_000,
}


class UserService:
    def __init__(
        self,
        client: FirestoreClient,
        *,
        storage: StorageClient | None = None,
        connections: "ConnectionService | None" = None,
    ) -> None:
        self.client = client
        self.storage = storage
        self.connections = connections

    def ensure_user(
        self,
        owner_uid: str,
        *,
        display_name: str | None = None,
        email: str | None = None,
        photo_url: str | None = None,
    ) -> dict[str, Any]:
        path = user_path(owner_uid)
        data = self.client.get_document(path)
        if data is None:
            now = datetime.now(UTC)
            data = {
                "uid": owner_uid,
                "displayName": display_name,
                "email": email,
                "photoUrl": photo_url,
                "onboarding": {
                    "status": OnboardingStatus.not_started.value,
                    "currentStep": None,
                    "answers": {},
                    "schemaVersion": 1,
                    "completedAt": None,
                },
                "persona": None,
                "preferences": dict(DEFAULT_PREFERENCES),
                "limits": dict(DEFAULT_LIMITS),
                "createdAt": now,
                "updatedAt": now,
            }
            self.client.set_document(path, data)
            return data

        changes: dict[str, Any] = {}
        for field, value in (
            ("displayName", display_name),
            ("email", email),
            ("photoUrl", photo_url),
        ):
            if value is not None and data.get(field) != value:
                changes[field] = value
        if changes:
            changes["updatedAt"] = datetime.now(UTC)
            self.client.update_document(path, changes)
            data.update(changes)
        return data

    def get_user(self, owner_uid: str) -> dict[str, Any]:
        return self.ensure_user(owner_uid)

    def to_me(self, owner_uid: str, data: dict[str, Any], *, read_only: bool = False) -> Me:
        onboarding = data.get("onboarding") or {}
        persona = data.get("persona") or {}
        preferences = data.get("preferences") or {}
        avatar = data.get("avatar")
        return Me(
            uid=owner_uid,
            displayName=data.get("displayName"),
            email=data.get("email"),
            onboardingCompleted=onboarding.get("status") == OnboardingStatus.completed.value,
            personaVersion=persona.get("version"),
            preferences=Preferences(
                timezone=preferences.get("timezone", "UTC"),
                defaultLanguage=preferences.get("defaultLanguage", "en"),
            ),
            avatar=AvatarState(**avatar) if isinstance(avatar, dict) else None,
            readOnly=read_only,
        )

    def save_avatar(self, owner_uid: str, avatar: AvatarState) -> AvatarState:
        """Persist the avatar on the user document so it follows the user everywhere."""
        self.ensure_user(owner_uid)
        self.client.update_document(
            user_path(owner_uid),
            {"avatar": avatar.model_dump(), "updatedAt": datetime.now(UTC)},
        )
        return avatar

    def get_onboarding(self, owner_uid: str) -> OnboardingState:
        data = self.get_user(owner_uid)
        onboarding = data.get("onboarding") or {}
        return OnboardingState(
            status=OnboardingStatus(
                onboarding.get("status", OnboardingStatus.not_started.value)
            ),
            currentStep=onboarding.get("currentStep"),
            answers=onboarding.get("answers") or {},
        )

    def save_onboarding_step(
        self, owner_uid: str, step: OnboardingStep
    ) -> OnboardingState:
        data = self.get_user(owner_uid)
        onboarding = dict(data.get("onboarding") or {})
        answers = dict(onboarding.get("answers") or {})
        answers.update(step.answers)

        status = onboarding.get("status", OnboardingStatus.not_started.value)
        if status != OnboardingStatus.completed.value:
            status = OnboardingStatus.in_progress.value

        onboarding.update(
            {
                "status": status,
                "currentStep": step.step,
                "answers": answers,
                "schemaVersion": onboarding.get("schemaVersion", 1),
            }
        )
        self.client.update_document(
            user_path(owner_uid),
            {"onboarding": onboarding, "updatedAt": datetime.now(UTC)},
        )
        return self.get_onboarding(owner_uid)

    def mark_onboarding_complete(self, owner_uid: str) -> None:
        data = self.get_user(owner_uid)
        onboarding = dict(data.get("onboarding") or {})
        now = datetime.now(UTC)
        onboarding.update(
            {
                "status": OnboardingStatus.completed.value,
                "completedAt": now,
                "schemaVersion": onboarding.get("schemaVersion", 1),
            }
        )
        self.client.update_document(
            user_path(owner_uid), {"onboarding": onboarding, "updatedAt": now}
        )

    def save_onboarding_research(
        self,
        owner_uid: str,
        *,
        links: list[str],
        answers: dict[str, Any],
        sources: list[dict[str, Any]],
        queries: list[str],
        search_suggestions: str,
        model: str,
    ) -> OnboardingState:
        """Merge grounded research results into the onboarding state.

        The links and grounding metadata live under `onboarding`, so they are covered by the
        account delete (the whole `users/{uid}` tree). `creatorLinks` also lands in `answers`
        so the form reloads with the links the user gave.
        """
        data = self.get_user(owner_uid)
        onboarding = dict(data.get("onboarding") or {})
        merged = dict(onboarding.get("answers") or {})
        merged.update(answers)
        merged["creatorLinks"] = links

        status = onboarding.get("status", OnboardingStatus.not_started.value)
        if status != OnboardingStatus.completed.value:
            status = OnboardingStatus.in_progress.value

        now = datetime.now(UTC)
        onboarding.update(
            {
                "status": status,
                "answers": merged,
                "research": {
                    "model": model,
                    "sources": sources,
                    "queries": queries,
                    "searchSuggestions": search_suggestions,
                    "updatedAt": now,
                },
                "schemaVersion": onboarding.get("schemaVersion", 1),
            }
        )
        self.client.update_document(
            user_path(owner_uid), {"onboarding": onboarding, "updatedAt": now}
        )
        return self.get_onboarding(owner_uid)

    def delete_account(self, owner_uid: str) -> None:
        """Remove the entire `users/{uid}` subtree and all stored objects. Idempotent.

        OAuth grants are revoked at the provider first: the tree delete destroys the only copy
        of the encrypted tokens. `revoke_all` is best-effort and never raises, so a provider
        failure cannot leave the account half-deleted.
        """
        if self.connections is not None:
            self.connections.revoke_all(owner_uid=owner_uid)
        if self.storage is not None:
            self.storage.delete_prefix(user_object_prefix(owner_uid))
        self.client.delete_document_tree(user_path(owner_uid))

    def set_persona(
        self,
        owner_uid: str,
        *,
        storage_path: str,
        version: int,
        language: str,
        approved_at: datetime,
    ) -> None:
        self.client.update_document(
            user_path(owner_uid),
            {
                "persona": {
                    "storagePath": storage_path,
                    "version": version,
                    "language": language,
                    "lastApprovedAt": approved_at,
                },
                "updatedAt": approved_at,
            },
        )
