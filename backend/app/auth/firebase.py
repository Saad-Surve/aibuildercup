from functools import lru_cache

import firebase_admin
from firebase_admin import auth

from app.config import get_settings


@lru_cache
def _ensure_app() -> firebase_admin.App:
    if not firebase_admin._apps:
        firebase_admin.initialize_app(
            options={"projectId": get_settings().firebase_project_id}
        )
    return firebase_admin.get_app()


def verify_id_token(token: str) -> dict:
    _ensure_app()
    return auth.verify_id_token(token)
