"""User profile and onboarding state.

The user document (`users/{uid}`) is the root of every user-owned path. It is created lazily on
the first authenticated request so the frontend never has to bootstrap it. Onboarding answers are
stored on the same document under `onboarding`.
"""

from datetime import UTC, datetime
from typing import Any

from app.schemas.onboarding import OnboardingState, OnboardingStatus, OnboardingStep
from app.schemas.users import Me, Preferences
from app.services.firestore_service import FirestoreClient, user_path
from app.services.paths import user_object_prefix
from app.services.storage_service import StorageClient

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
        self, client: FirestoreClient, *, storage: StorageClient | None = None
    ) -> None:
        self.client = client
        self.storage = storage

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

    def to_me(self, owner_uid: str, data: dict[str, Any]) -> Me:
        onboarding = data.get("onboarding") or {}
        persona = data.get("persona") or {}
        preferences = data.get("preferences") or {}
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
        )

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

    def delete_account(self, owner_uid: str) -> None:
        """Remove the entire `users/{uid}` subtree and all stored objects. Idempotent."""
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
