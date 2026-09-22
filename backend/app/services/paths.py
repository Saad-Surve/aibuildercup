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


def user_object_prefix(uid: str) -> str:
    """Object-name prefix that scopes every stored object to one user."""
    return f"{user_path(uid)}/"


def projects_collection_path(uid: str) -> str:
    return f"{user_path(uid)}/projects"


def project_path(uid: str, project_id: str) -> str:
    return f"{projects_collection_path(uid)}/{safe_segment(project_id, name='projectId')}"


def assets_collection_path(uid: str, project_id: str) -> str:
    return f"{project_path(uid, project_id)}/assets"


def asset_path(uid: str, project_id: str, asset_id: str) -> str:
    return (
        f"{assets_collection_path(uid, project_id)}/"
        f"{safe_segment(asset_id, name='assetId')}"
    )


def jobs_collection_path(uid: str, project_id: str) -> str:
    return f"{project_path(uid, project_id)}/jobs"


def job_path(uid: str, project_id: str, job_id: str) -> str:
    return (
        f"{jobs_collection_path(uid, project_id)}/"
        f"{safe_segment(job_id, name='jobId')}"
    )


def source_object_path(
    uid: str, project_id: str, asset_id: str, extension: str
) -> str:
    """Object path for an uploaded source video: `.../source/{assetId}.{ext}`."""
    segment = safe_segment(asset_id, name="assetId")
    ext = extension.lower().lstrip(".")
    if not ext.isalnum():
        raise InvalidPathSegment(f"Invalid extension: {extension!r}")
    return f"{project_path(uid, project_id)}/source/{segment}.{ext}"


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


def transcripts_collection_path(uid: str, project_id: str) -> str:
    return f"{project_path(uid, project_id)}/transcripts"


def transcript_path(uid: str, project_id: str, transcript_id: str) -> str:
    return (
        f"{transcripts_collection_path(uid, project_id)}/"
        f"{safe_segment(transcript_id, name='transcriptId')}"
    )


def transcript_object_path(uid: str, project_id: str, version: int) -> str:
    """Canonical transcript JSON in Cloud Storage."""
    return f"{project_path(uid, project_id)}/transcripts/v{version}.json"


def transcript_vtt_object_path(uid: str, project_id: str, language: str) -> str:
    """Derived caption file in Cloud Storage."""
    safe_language = safe_segment(language.replace("-", "_"), name="language")
    return f"{project_path(uid, project_id)}/captions/{safe_language}.vtt"
