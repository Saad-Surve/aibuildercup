"""Project glossary persistence.

A glossary is the creator's own terminology for one project (product names, catchphrases,
spellings they insist on). It lives at `users/{uid}/projects/{projectId}/glossary/main`, so
the existing recursive project delete removes it with no extra wiring.

The worker reads the applicable terms for the target language when it localizes, and records
the glossary version it used on the localization so a result stays reproducible.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from app.errors import ConflictError
from app.schemas.localizations import Glossary, GlossaryTerm, GlossaryUpdate
from app.services.dubbing import base_code
from app.services.firestore_service import FirestoreClient, glossary_path
from app.services.project_service import ProjectService


def _to_glossary(project_id: str, data: dict[str, Any]) -> Glossary:
    raw_terms = data.get("terms")
    terms: list[GlossaryTerm] = []
    if isinstance(raw_terms, list):
        for item in raw_terms:
            if isinstance(item, dict) and item.get("source") and item.get("target"):
                terms.append(
                    GlossaryTerm(
                        source=str(item["source"]),
                        target=str(item["target"]),
                        targetLanguage=str(item.get("targetLanguage") or ""),
                    )
                )
    return Glossary(
        projectId=project_id,
        sourceLanguage=str(data.get("sourceLanguage") or "en"),
        terms=terms,
        version=int(data.get("version") or 0),
        updatedAt=data.get("updatedAt"),
    )


def _normalise(payload: GlossaryUpdate) -> list[GlossaryTerm]:
    seen: set[tuple[str, str, str]] = set()
    terms: list[GlossaryTerm] = []
    for term in payload.terms:
        source = term.source.strip()
        target = term.target.strip()
        if not source or not target:
            continue
        language = base_code(term.targetLanguage) if term.targetLanguage else ""
        key = (source.casefold(), target, language)
        if key in seen:
            continue
        seen.add(key)
        terms.append(
            GlossaryTerm(source=source, target=target, targetLanguage=language)
        )
    return terms


class GlossaryService:
    def __init__(
        self, client: FirestoreClient, *, projects: ProjectService
    ) -> None:
        self.client = client
        self.projects = projects

    def get(self, *, owner_uid: str, project_id: str) -> Glossary:
        """The project glossary; an empty, version-0 glossary when none exists yet."""
        self.projects.get(owner_uid=owner_uid, project_id=project_id)
        data = self.client.get_document(glossary_path(owner_uid, project_id))
        if data is None or data.get("ownerUid") != owner_uid:
            return Glossary(projectId=project_id)
        return _to_glossary(project_id, data)

    def put(
        self, *, owner_uid: str, project_id: str, payload: GlossaryUpdate
    ) -> Glossary:
        """Replace the glossary, bumping its version.

        `expectedVersion`, when supplied, is an optimistic-concurrency guard: a stale client
        gets a 409 instead of silently overwriting a newer glossary.
        """
        self.projects.get(owner_uid=owner_uid, project_id=project_id)
        path = glossary_path(owner_uid, project_id)
        existing = self.client.get_document(path)
        if existing is None or existing.get("ownerUid") != owner_uid:
            existing = None
        current_version = int((existing or {}).get("version") or 0)
        if (
            payload.expectedVersion is not None
            and payload.expectedVersion != current_version
        ):
            raise ConflictError(
                "The glossary changed since it was loaded.",
                code="GLOSSARY_VERSION_CONFLICT",
                details={
                    "expectedVersion": payload.expectedVersion,
                    "currentVersion": current_version,
                },
            )

        now = datetime.now(UTC)
        document: dict[str, Any] = {
            "ownerUid": owner_uid,
            "projectId": project_id,
            "sourceLanguage": payload.sourceLanguage,
            "terms": [term.model_dump() for term in _normalise(payload)],
            "version": current_version + 1,
            "createdAt": (existing or {}).get("createdAt", now),
            "updatedAt": now,
        }
        self.client.set_document(path, document)
        return _to_glossary(project_id, document)

    def applicable(
        self, *, owner_uid: str, project_id: str, target_language: str
    ) -> tuple[list[GlossaryTerm], int]:
        """Terms that apply to a target language, plus the glossary version.

        A term with no `targetLanguage` applies to every target; otherwise the base codes
        must match (`hi-IN` matches `hi`).
        """
        data = self.client.get_document(glossary_path(owner_uid, project_id))
        if data is None or data.get("ownerUid") != owner_uid:
            return [], 0
        wanted = base_code(target_language)
        terms = [
            term
            for term in _to_glossary(project_id, data).terms
            if not term.targetLanguage or base_code(term.targetLanguage) == wanted
        ]
        return terms, int(data.get("version") or 0)


__all__ = ["GlossaryService"]
