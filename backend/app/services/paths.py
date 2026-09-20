"""Canonical document and object path builders.

Paths are pure functions and every id is validated as a single path segment, so a uid or
document id can never escape its segment (`../`, `/`, spaces, dots are rejected). These paths
are shared by the Firestore and Cloud Storage layers.
"""

import re

_SEGMENT = re.compile(r"^[A-Za-z0-9_-]{1,128}$")


class InvalidPathSegment(ValueError):
    """Raised when an id could escape its path segment."""


def safe_segment(value: str, *, name: str) -> str:
    if not _SEGMENT.match(value):
        raise InvalidPathSegment(f"Invalid {name}: {value!r}")
    return value


def user_path(uid: str) -> str:
    return f"users/{safe_segment(uid, name='uid')}"


def projects_collection_path(uid: str) -> str:
    return f"{user_path(uid)}/projects"


def project_path(uid: str, project_id: str) -> str:
    return f"{projects_collection_path(uid)}/{safe_segment(project_id, name='projectId')}"


def persona_revisions_collection_path(uid: str) -> str:
    return f"{user_path(uid)}/personaRevisions"


def persona_revision_path(uid: str, revision_id: str) -> str:
    return (
        f"{persona_revisions_collection_path(uid)}/"
        f"{safe_segment(revision_id, name='revisionId')}"
    )


def persona_object_path(uid: str) -> str:
    return f"{user_path(uid)}/profile/persona.md"


def persona_revision_object_path(uid: str, version: int) -> str:
    return f"{user_path(uid)}/profile/revisions/persona-v{version}.md"
