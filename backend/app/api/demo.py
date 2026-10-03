"""Public read-only demo session.

Visitors enter the shared demo account without ever seeing a password: this endpoint ensures the
demo Auth user exists and returns a short-lived Firebase custom token for it. The UID is listed
in `read_only_user_uids`, so the API still rejects every mutating request it makes; this endpoint
only mints a session.

The endpoint is unauthenticated by design (it is the demo's front door). It is disabled unless
`DEMO_USER_UID` is configured.
"""

from fastapi import APIRouter

from app.auth.firebase import create_custom_token, ensure_user
from app.config import get_settings
from app.errors import NotFoundError

router = APIRouter(tags=["demo"])


@router.post("/demo/session")
async def create_demo_session() -> dict[str, str]:
    settings = get_settings()
    if not settings.demo_user_uid:
        raise NotFoundError("The demo account is not configured.")
    # Self-heal: a visitor could delete the public Auth user from the client SDK. Its content
    # lives under `users/{uid}` in Firestore/Cloud Storage and survives; recreating the Auth
    # user here restores the demo on the next click.
    ensure_user(settings.demo_user_uid, display_name="Demo Creator")
    return {"token": create_custom_token(settings.demo_user_uid)}
