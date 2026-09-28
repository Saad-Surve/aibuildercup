"""Persona generation, storage, and versioned edits.

Onboarding answers become a `persona.md` written to Cloud Storage with metadata on the user
document. Generation goes through the LLM provider; if the call fails a deterministic template
keeps onboarding working. Every version is also written as an immutable revision object and a
`personaRevisions` document.
"""

import json
import logging
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from app.config import Settings
from app.errors import ConflictError, NotFoundError
from app.providers.base import LlmProvider
from app.schemas.persona import Persona, PersonaRef
from app.services.firestore_service import FirestoreClient
from app.services.markdown_repair import normalize_markdown
from app.services.paths import (
    persona_object_path,
    persona_revision_object_path,
    persona_revision_path,
)
from app.services.storage_service import StorageClient
from app.services.user_service import UserService

logger = logging.getLogger(__name__)

PERSONA_PROMPT_VERSION = "persona-v1"

PERSONA_SYSTEM = (
    "You are a creator strategist. Turn the creator's onboarding answers into a concise, "
    "actionable persona document in Markdown. Use these sections: Identity, Audience, Voice, "
    "Platforms, Review Priorities. Be specific and avoid generic filler. Never invent facts the "
    "creator did not provide."
)

PERSONA_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {"markdown": {"type": "string"}},
    "required": ["markdown"],
}


def build_persona_markdown(answers: dict[str, Any]) -> str:
    name = str(answers.get("creatorName") or "The creator").strip()
    topics = [str(topic) for topic in (answers.get("topics") or [])]
    platforms = [str(platform) for platform in (answers.get("platforms") or [])]
    audience = str(
        answers.get("audience") or "a general audience looking for practical advice"
    ).strip()
    language = str(answers.get("primaryLanguage") or "en").strip()

    lines = [
        f"# Creator Persona — {name}",
        "",
        "## Identity",
        f"- Name: {name}",
        f"- Primary language: {language}",
    ]
    if topics:
        lines.append(f"- Topics: {', '.join(topics)}")

    lines += [
        "",
        "## Audience",
        f"- {audience}",
        "",
        "## Voice",
        "- Clear, direct, and practical.",
        "- Leads with concrete examples over abstract advice.",
    ]
    if platforms:
        lines += ["", "## Platforms", *[f"- {platform}" for platform in platforms]]

    lines += [
        "",
        "## Review Priorities",
        "- Accuracy first: never overstate certainty.",
        "- Keep hooks honest and specific.",
        "- Respect local language and cultural context.",
    ]
    return "\n".join(lines).strip() + "\n"


class PersonaService:
    def __init__(
        self,
        *,
        client: FirestoreClient,
        storage: StorageClient,
        llm: LlmProvider,
        users: UserService,
        settings: Settings,
    ) -> None:
        self.client = client
        self.storage = storage
        self.llm = llm
        self.users = users
        self.settings = settings

    async def complete_onboarding(self, owner_uid: str) -> PersonaRef:
        self.users.ensure_user(owner_uid)
        answers = self.users.get_onboarding(owner_uid).answers
        markdown = await self._generate_markdown(answers)

        now = datetime.now(UTC)
        canonical_path, revision_path = self._persist(owner_uid, markdown, version=1)
        language = str(answers.get("primaryLanguage") or "en")
        self.users.set_persona(
            owner_uid,
            storage_path=canonical_path,
            version=1,
            language=language,
            approved_at=now,
        )
        self._write_revision(
            owner_uid,
            version=1,
            storage_path=revision_path,
            change_type="initial",
            change_summary="Initial persona generated during onboarding.",
            source="onboarding",
            created_at=now,
        )
        self.users.mark_onboarding_complete(owner_uid)
        return PersonaRef(
            onboardingCompleted=True,
            personaVersion=1,
            personaStoragePath=canonical_path,
        )

    def get(self, owner_uid: str) -> Persona:
        persona = self._persona_metadata(owner_uid)
        content = normalize_markdown(self.storage.download_text(persona["storagePath"]))
        return Persona(
            version=persona["version"],
            content=content,
            storagePath=persona["storagePath"],
        )

    def update(self, owner_uid: str, *, content: str, expected_version: int) -> Persona:
        persona = self._persona_metadata(owner_uid)
        current_version = persona["version"]
        if current_version != expected_version:
            raise ConflictError(
                "Persona was updated elsewhere",
                code="PERSONA_VERSION_CONFLICT",
                details={
                    "expectedVersion": expected_version,
                    "currentVersion": current_version,
                },
            )

        new_version = current_version + 1
        now = datetime.now(UTC)
        content = normalize_markdown(content)
        canonical_path, revision_path = self._persist(
            owner_uid, content, version=new_version
        )
        self.users.set_persona(
            owner_uid,
            storage_path=canonical_path,
            version=new_version,
            language=persona.get("language", "en"),
            approved_at=now,
        )
        self._write_revision(
            owner_uid,
            version=new_version,
            storage_path=revision_path,
            change_type="approved_update",
            change_summary="User-approved persona edit.",
            source="user_edit",
            created_at=now,
        )
        return Persona(
            version=new_version, content=content, storagePath=canonical_path
        )

    def _persona_metadata(self, owner_uid: str) -> dict[str, Any]:
        persona = self.users.get_user(owner_uid).get("persona") or {}
        if not persona.get("storagePath") or not persona.get("version"):
            raise NotFoundError("Persona not found", code="PERSONA_NOT_FOUND")
        return persona

    def _persist(
        self, owner_uid: str, markdown: str, *, version: int
    ) -> tuple[str, str]:
        canonical_path = persona_object_path(owner_uid)
        revision_path = persona_revision_object_path(owner_uid, version)
        self.storage.upload_text(canonical_path, markdown)
        self.storage.upload_text(revision_path, markdown)
        return canonical_path, revision_path

    def _write_revision(
        self,
        owner_uid: str,
        *,
        version: int,
        storage_path: str,
        change_type: str,
        change_summary: str,
        source: str,
        created_at: datetime,
    ) -> None:
        self.client.set_document(
            persona_revision_path(owner_uid, uuid4().hex),
            {
                "ownerUid": owner_uid,
                "version": version,
                "storagePath": storage_path,
                "changeType": change_type,
                "changeSummary": change_summary,
                "source": source,
                "approvalStatus": "approved",
                "approvedBy": "user",
                "createdAt": created_at,
            },
        )

    async def _generate_markdown(self, answers: dict[str, Any]) -> str:
        try:
            completion = await self.llm.complete_json(
                model=self.settings.model_orchestrator,
                prompt_version=PERSONA_PROMPT_VERSION,
                system=PERSONA_SYSTEM,
                user=json.dumps(answers, sort_keys=True, default=str),
                schema=PERSONA_SCHEMA,
            )
            markdown = completion.data.get("markdown")
            if isinstance(markdown, str) and markdown.strip():
                return normalize_markdown(markdown).strip() + "\n"
            logger.warning("Persona provider returned no markdown; using template")
        except Exception:  # noqa: BLE001
            logger.exception("Persona generation failed; using deterministic template")
        return build_persona_markdown(answers)
