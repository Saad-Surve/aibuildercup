"""Pub/Sub push handlers for internal pipeline events.

The GCS `object finalized` notification is the trigger of record for transcription (design
diagrams 4/5): object finalized -> `video-events` -> push subscription -> this handler ->
`run_transcribe`. Ownership is recovered from the object path, and the same idempotent transcribe
job as `POST /assets/{id}/complete` is reused, so the two paths converge.
"""

import base64
import json
import logging
from typing import Any

from app.errors import NotFoundError
from app.schemas.jobs import JobStatus
from app.services.firestore_service import parse_source_object_path
from app.workers.transcribe_worker import run_transcribe

logger = logging.getLogger(__name__)


class InvalidPubSubMessage(ValueError):
    """Raised when a push envelope cannot be decoded into an event payload."""


def decode_push_envelope(body: dict[str, Any]) -> dict[str, Any]:
    """Decode a Pub/Sub push request body into the published JSON payload."""
    message = body.get("message")
    if not isinstance(message, dict):
        raise InvalidPubSubMessage("push body has no message")
    data = message.get("data")
    if not isinstance(data, str) or not data:
        raise InvalidPubSubMessage("push message has no data")
    try:
        payload = json.loads(base64.b64decode(data))
    except Exception as exc:  # noqa: BLE001 - any decode failure is a bad message
        raise InvalidPubSubMessage("push message data is not base64 JSON") from exc
    if not isinstance(payload, dict):
        raise InvalidPubSubMessage("push message payload is not an object")
    return payload


def source_object_from_event(payload: dict[str, Any]) -> tuple[str, str, str] | None:
    """Return `(uid, project_id, asset_id)` when the event is a source-video finalize."""
    name = payload.get("name")
    if not isinstance(name, str):
        return None
    return parse_source_object_path(name)


async def handle_video_finalized(
    payload: dict[str, Any], *, dependencies: dict[str, Any]
) -> str | None:
    """Handle one GCS-finalized event. Returns the job id that ran, or None if ignored.

    Only runs when the transcribe job is still `queued`: if `POST /assets/{id}/complete`
    already ran the worker (or the object is not a source video), the event is a no-op.
    """
    parsed = source_object_from_event(payload)
    if parsed is None:
        return None
    owner_uid, project_id, asset_id = parsed

    assets = dependencies["assets"]
    try:
        job = assets.queue_transcription(
            owner_uid=owner_uid, project_id=project_id, asset_id=asset_id
        )
    except NotFoundError:
        logger.warning("video event for unknown asset %s; ignoring", asset_id)
        return None

    if job.status.value != JobStatus.queued.value:
        logger.info(
            "video event for %s: job %s is %s; skipping", asset_id, job.jobId, job.status.value
        )
        return None

    await run_transcribe(
        owner_uid=owner_uid, project_id=project_id, job_id=job.jobId, **dependencies
    )
    return job.jobId
