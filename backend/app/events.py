"""Internal event envelope and topic routing.

Matches `contracts/events.md` and the event table in `docs/technical-design/api-design.md`
section 16. Events are the coupling between the API and the workers; the envelope is stable so
consumers can be added without renegotiating message shapes.
"""

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

EVENT_SCHEMA_VERSION = 1

# Event type -> Pub/Sub topic name. Topic names mirror `infra/pubsub.tf`.
TOPIC_BY_EVENT = {
    "video.uploaded": "video-events",
    "transcription.requested": "transcription-events",
    "transcript.ready": "transcription-events",
    "analysis.requested": "analysis-events",
    "reviewer.completed": "analysis-events",
    "analysis.ready": "analysis-events",
    "social.sync.requested": "social-sync-events",
    "social.sync.completed": "social-sync-events",
    "artifact.requested": "artifact-events",
    "artifact.ready": "artifact-events",
    "localization.requested": "localization-events",
    "localization.ready": "localization-events",
}


class UnknownEventType(ValueError):
    """Raised when an event type has no topic mapping."""


def topic_for_event(event_type: str) -> str:
    try:
        return TOPIC_BY_EVENT[event_type]
    except KeyError as exc:
        raise UnknownEventType(f"No topic mapped for event type {event_type!r}") from exc


def build_event(
    *,
    event_type: str,
    owner_uid: str,
    project_id: str,
    job_id: str | None = None,
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build the canonical event envelope."""
    return {
        "eventId": uuid4().hex,
        "type": event_type,
        "ownerUid": owner_uid,
        "projectId": project_id,
        "jobId": job_id,
        "payload": payload or {},
        "occurredAt": datetime.now(UTC).isoformat(),
        "schemaVersion": EVENT_SCHEMA_VERSION,
    }
