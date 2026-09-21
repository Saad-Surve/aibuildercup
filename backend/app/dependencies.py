from collections.abc import Callable
from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.auth.firebase import delete_user as firebase_delete_user
from app.auth.firebase import verify_id_token
from app.config import get_settings
from app.providers import get_providers
from app.services.asset_service import AssetService
from app.services.firestore_service import get_firestore_client
from app.services.job_service import JobService
from app.services.persona_service import PersonaService
from app.services.project_service import ProjectService
from app.services.storage_service import get_storage_client
from app.services.user_service import UserService


@dataclass(frozen=True)
class AuthenticatedUser:
    uid: str
    email: str | None
    display_name: str | None = None
    picture: str | None = None


def get_project_service() -> ProjectService:
    return ProjectService(get_firestore_client())


def get_job_service() -> JobService:
    return JobService(get_firestore_client())


def get_asset_service() -> AssetService:
    client = get_firestore_client()
    return AssetService(
        client,
        projects=ProjectService(client),
        jobs=JobService(client),
        storage=get_storage_client(),
        settings=get_settings(),
    )


def get_user_service() -> UserService:
    return UserService(get_firestore_client(), storage=get_storage_client())


def get_identity_deleter() -> Callable[[str], None]:
    """Deletes the Firebase Auth account. Injected so tests can override it."""
    return firebase_delete_user


def get_persona_service() -> PersonaService:
    return PersonaService(
        client=get_firestore_client(),
        storage=get_storage_client(),
        llm=get_providers().llm,
        users=get_user_service(),
        settings=get_settings(),
    )


# Declared as a security scheme so Swagger UI shows an "Authorize" button and every
# protected route carries the bearer requirement in the generated OpenAPI document.
bearer_scheme = HTTPBearer(
    auto_error=False,
    scheme_name="FirebaseBearer",
    bearerFormat="Firebase ID token",
)

BearerCredentials = Annotated[
    HTTPAuthorizationCredentials | None, Depends(bearer_scheme)
]


async def current_user(credentials: BearerCredentials) -> AuthenticatedUser:
    if credentials is None or not credentials.credentials:
        raise HTTPException(status_code=401, detail="Missing bearer token")
    try:
        decoded = verify_id_token(credentials.credentials)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=401, detail="Invalid token") from exc
    return AuthenticatedUser(
        uid=decoded["uid"],
        email=decoded.get("email"),
        display_name=decoded.get("name"),
        picture=decoded.get("picture"),
    )
