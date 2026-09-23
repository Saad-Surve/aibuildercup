"""Internal Pub/Sub push endpoints.

These are not part of the public API: they authenticate with a Pub/Sub push OIDC token (see
`app.auth.pubsub`) rather than a Firebase ID token, and are registered without the client-facing
bearer requirement.
"""

import logging

from fastapi import APIRouter, HTTPException, Request, Response, status

from app.auth.pubsub import verify_pubsub_push
from app.workers.pubsub_handlers import (
    InvalidPubSubMessage,
    decode_push_envelope,
    handle_video_finalized,
)
from app.workers.transcribe_worker import live_worker_dependencies

logger = logging.getLogger(__name__)

router = APIRouter(tags=["internal"])


@router.post("/internal/pubsub/video-events", status_code=status.HTTP_204_NO_CONTENT)
async def video_events(request: Request) -> Response:
    """Receive GCS `object finalized` notifications and run the transcribe worker."""
    verify_pubsub_push(request.headers.get("authorization"))

    try:
        body = await request.json()
    except Exception:  # noqa: BLE001 - ack malformed bodies so Pub/Sub stops retrying
        logger.warning("ignoring non-JSON Pub/Sub push body")
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    try:
        payload = decode_push_envelope(body)
    except InvalidPubSubMessage as exc:
        logger.warning("ignoring malformed Pub/Sub message: %s", exc)
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    try:
        await handle_video_finalized(payload, dependencies=live_worker_dependencies())
    except Exception as exc:  # noqa: BLE001 - surface to Pub/Sub so the message is retried
        logger.exception("video-events handler failed")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Event handling failed",
        ) from exc

    return Response(status_code=status.HTTP_204_NO_CONTENT)
