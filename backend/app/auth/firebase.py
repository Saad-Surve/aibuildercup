from functools import lru_cache
from threading import Lock

import firebase_admin
from firebase_admin import auth

from app.config import get_settings

_app_lock = Lock()


@lru_cache
def _ensure_app() -> firebase_admin.App:
    with _app_lock:
        if not firebase_admin._apps:
            settings = get_settings()
            # The `serviceAccountId` is what lets the Admin SDK sign custom tokens through the IAM
            # signBlob API instead of requiring a downloaded private key. On Cloud Run the runtime
            # The service account signs as itself (`api_sign_blob` in infra/iam.tf).
            # Locally, Application Default Credentials sign as it too, so the developer needs
            # `roles/iam.serviceAccountTokenCreator` on this service account.
            service_account = (
                settings.storage_signing_service_account
                or f"creator-studio-api@{settings.project_id}.iam.gserviceaccount.com"
            )
            firebase_admin.initialize_app(
                options={
                    "projectId": settings.firebase_project_id,
                    "serviceAccountId": service_account,
                }
            )
        return firebase_admin.get_app()


def verify_id_token(token: str) -> dict:
    _ensure_app()
    return auth.verify_id_token(token)


def create_custom_token(uid: str) -> str:
    """Mint a Firebase custom token so a client can sign in as `uid` without a password."""
    _ensure_app()
    token = auth.create_custom_token(uid)
    return token.decode("utf-8") if isinstance(token, bytes) else token


def ensure_user(uid: str, *, display_name: str | None = None) -> None:
    """Create the user when missing and reset the fields we control.

    The demo account is public, so a visitor could delete it from the client SDK. Its content
    lives in Firestore/Cloud Storage and is untouched by an Auth deletion; recreating the Auth
    user here makes the very next demo sign-in self-heal.
    """
    _ensure_app()
    try:
        user = auth.get_user(uid)
    except auth.UserNotFoundError:
        auth.create_user(uid=uid, display_name=display_name)
        return
    if display_name is not None and user.display_name != display_name:
        auth.update_user(uid, display_name=display_name)


def delete_user(uid: str) -> None:
    _ensure_app()
    auth.delete_user(uid)
