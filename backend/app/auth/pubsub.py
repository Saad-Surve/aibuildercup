"""Pub/Sub push authentication.

Pub/Sub push subscriptions can mint an OIDC token for the subscriber endpoint. When an audience
is configured we verify that token, so the internal push endpoint cannot be driven by arbitrary
callers even though the Cloud Run service is otherwise unauthenticated.
"""

import logging

from app.config import get_settings
from app.errors import UnauthorizedError

logger = logging.getLogger(__name__)


def verify_pubsub_push(authorization: str | None) -> None:
    """Raise `UnauthorizedError` unless the push request is a valid Pub/Sub OIDC push.

    Verification is skipped when no audience is configured (local development).
    """
    settings = get_settings()
    audience = settings.pubsub_push_audience
    if not audience:
        return
    # The infra subscription mints the token for the trimmed URL; normalise both sides.
    audience = audience.rstrip("/")

    if not authorization or not authorization.lower().startswith("bearer "):
        raise UnauthorizedError("Missing Pub/Sub push token")

    token = authorization.split(" ", 1)[1].strip()
    try:
        from google.auth.transport import requests as google_requests
        from google.oauth2 import id_token

        claims = id_token.verify_oauth2_token(
            token, google_requests.Request(), audience=audience
        )
    except Exception as exc:  # noqa: BLE001 - any verification failure is a 401
        logger.warning("Pub/Sub push token rejected: %s", exc)
        raise UnauthorizedError("Invalid Pub/Sub push token") from exc

    expected = settings.pubsub_push_service_account
    if expected and claims.get("email") != expected:
        raise UnauthorizedError("Pub/Sub push token from an unexpected account")
