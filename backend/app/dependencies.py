from collections.abc import Callable
from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.auth.firebase import delete_user as firebase_delete_user
from app.auth.firebase import verify_id_token
from app.config import get_settings
from app.providers import get_providers
from app.services.analysis_service import AnalysisService
from app.services.asset_service import AssetService
from app.services.caption_service import CaptionRenderService
from app.services.draft_service import DraftService
from app.services.firestore_service import get_firestore_client
from app.services.glossary_service import GlossaryService
from app.services.job_service import JobService
from app.services.localization_service import LocalizationService
from app.services.persona_service import PersonaService
from app.services.project_service import ProjectService
from app.services.pubsub_service import PubSubClient, get_pubsub_client
from app.services.storage_service import get_storage_client
from app.services.thumbnail_service import ThumbnailService
from app.services.transcript_service import TranscriptService
from app.services.user_service import UserService
from app.workers.analysis_worker import analysis_after_response
from app.workers.caption_worker import caption_render_after_response
from app.workers.dub_worker import dub_after_response
from app.workers.thumbnail_worker import thumbnail_after_response
from app.workers.transcribe_worker import transcribe_after_response


@dataclass(frozen=True)
class AuthenticatedUser:
    uid: str
    email: str | None
    display_name: str | None = None
    picture: str | None = None


def get_project_service() -> ProjectService:
    return ProjectService(get_firestore_client(), storage=get_storage_client())


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


def get_transcript_service() -> TranscriptService:
    return TranscriptService(get_firestore_client(), storage=get_storage_client())


def get_draft_service() -> DraftService:
    client = get_firestore_client()
    return DraftService(
        client,
        projects=ProjectService(client),
        llm=get_providers().llm,
        settings=get_settings(),
    )


def get_caption_service() -> CaptionRenderService:
    client = get_firestore_client()
    storage = get_storage_client()
    projects = ProjectService(client, storage=storage)
    transcripts = TranscriptService(client, storage=storage)
    return CaptionRenderService(
        client,
        projects=projects,
        jobs=JobService(client),
        transcripts=transcripts,
        storage=storage,
        url_ttl_seconds=get_settings().upload_url_ttl_seconds,
    )


def get_thumbnail_service() -> ThumbnailService:
    client = get_firestore_client()
    storage = get_storage_client()
    settings = get_settings()
    projects = ProjectService(client, storage=storage)
    return ThumbnailService(
        client,
        projects=projects,
        jobs=JobService(client),
        storage=storage,
        url_ttl_seconds=settings.upload_url_ttl_seconds,
        price_per_image_usd=settings.imagegen_price_per_image_usd,
        max_project_cost_usd=settings.max_project_cost_usd,
    )


# (background_tasks, *, owner_uid, project_id, job_id) -> None. Injected so tests can
# record scheduling without running the worker.
ThumbnailScheduler = Callable[..., None]


def get_thumbnail_scheduler() -> ThumbnailScheduler:
    return thumbnail_after_response


# (background_tasks, *, owner_uid, project_id, job_id) -> None. Injected so tests can
# record scheduling without running the worker.
CaptionScheduler = Callable[..., None]


def get_caption_scheduler() -> CaptionScheduler:
    return caption_render_after_response


def get_localization_service() -> LocalizationService:
    client = get_firestore_client()
    storage = get_storage_client()
    projects = ProjectService(client, storage=storage)
    transcripts = TranscriptService(client, storage=storage)
    return LocalizationService(
        client,
        projects=projects,
        jobs=JobService(client),
        transcripts=transcripts,
        glossaries=get_glossary_service(),
        storage=storage,
        url_ttl_seconds=get_settings().upload_url_ttl_seconds,
    )


def get_glossary_service() -> GlossaryService:
    client = get_firestore_client()
    return GlossaryService(
        client, projects=ProjectService(client, storage=get_storage_client())
    )


# (background_tasks, *, owner_uid, project_id, job_id) -> None. Injected so tests can
# record scheduling without running the worker.
DubScheduler = Callable[..., None]


def get_dub_scheduler() -> DubScheduler:
    return dub_after_response


# (background_tasks, *, owner_uid, project_id, job_id) -> None. Injected so tests can
# record scheduling without running the worker.
TranscribeScheduler = Callable[..., None]


def get_transcribe_scheduler() -> TranscribeScheduler:
    return transcribe_after_response


def get_analysis_service() -> AnalysisService:
    client = get_firestore_client()
    return AnalysisService(client, jobs=JobService(client), settings=get_settings())


# (background_tasks, *, owner_uid, project_id, job_id) -> None. Injected so tests can
# record scheduling without running the worker.
AnalysisScheduler = Callable[..., None]


def get_analysis_scheduler() -> AnalysisScheduler:
    return analysis_after_response


def get_analysis_pubsub() -> PubSubClient | None:
    """Event publisher for the analysis API. Overridable in tests."""
    return get_pubsub_client()


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
