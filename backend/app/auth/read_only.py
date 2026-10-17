"""Read-only demo enforcement.

A demo account is a normal Firebase user (its UID is listed in
`settings.read_only_user_uids`) that may browse everything it owns but may never change it.
This module is the *hard* half of the guarantee: the HTTP layer rejects any mutating request
from a read-only UID with a 403 before a router or service can run. The web UI additionally
disables the matching controls, but that is a convenience — this is the enforcement.

The check is deliberately independent of route wiring: a new mutating endpoint is covered the
moment it is added, with no per-route annotation to forget. The only exceptions are POST
endpoints that do not mutate anything (currently the bulk thumbnail ZIP download); they are
allow-listed by path below.
"""

import re

from app.auth.firebase import verify_id_token
from app.config import get_settings

WRITE_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})

#: Shown to the user in the 403 body and mirrored (as `READ_ONLY_REASON`) in the web client.
READ_ONLY_MESSAGE = (
    "This is the read-only demo account. Changes are disabled."
)

#: `POST`s that only read. Matching is on the full request path.
_ALLOWED_READ_ONLY_POSTS = (
    # `POST /api/projects/{projectId}/thumbnails/download` zips already-stored images.
    re.compile(r"^/api/projects/[^/]+/thumbnails/download$"),
    # Minting a fresh demo session is not a data change.
    re.compile(r"^/api/demo/session$"),
)


def is_write_method(method: str) -> bool:
    return method.upper() in WRITE_METHODS


def is_read_only_allowed(path: str) -> bool:
    """True when a mutating method on `path` is actually a read (safe for the demo)."""
    return any(pattern.match(path) for pattern in _ALLOWED_READ_ONLY_POSTS)


def write_token_claims(token: str) -> dict | None:
    """Verify a write request's token so middleware and dependencies can share it.

    A missing, invalid, or expired token returns None: the request then falls through to the
    router, which returns its own 401 for protected routes. We never reject a request here
    because of a token problem — only because the (valid) identity is read-only.
    """
    if not get_settings().read_only_user_uids:
        return None
    try:
        decoded = verify_id_token(token)
    except Exception:  # noqa: BLE001 - invalid token is the router's problem, not ours
        return None
    return decoded
