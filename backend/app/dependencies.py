from collections.abc import Callable
from dataclasses import dataclass
from functools import lru_cache
from typing import Annotated

from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.auth.firebase import delete_user as firebase_delete_user
from app.auth.firebase import verify_id_token
from app.config import get_settings
from app.providers import get_providers
from app.services.analysis_service import AnalysisService
from app.services.asset_service import AssetService
from app.services.caption_service import CaptionRenderService
from app.services.channel_content_service import ChannelContentService
from app.services.connection_service import ConnectionService
from app.services.creator_import_service import CreatorImportService
from app.services.creator_library_service import CreatorLibraryService
from app.services.draft_service import DraftService
from app.services.firestore_service import get_firestore_client
from app.services.glossary_service import GlossaryService
from app.services.job_service import JobService
from app.services.localization_service import LocalizationService
from app.services.persona_research import PersonaResearchService
from app.services.persona_service import PersonaService
from app.services.project_service import ProjectService
from app.services.publish_service import PublishService
from app.services.pubsub_service import PubSubClient, get_pubsub_client
from app.services.schedule_service import ScheduleService
from app.services.storage_service import get_storage_client
from app.services.thumbnail_service import ThumbnailService
from app.services.token_cipher import TokenCipher, build_token_cipher
from app.services.transcript_service import TranscriptService
from app.services.user_service import UserService
from app.workers.analysis_worker import analysis_after_response
from app.workers.caption_worker import caption_render_after_response
from app.workers.dub_worker import dub_after_response
from app.workers.publish_worker import publish_after_response
from app.workers.thumbnail_worker import thumbnail_after_response
from app.workers.transcribe_worker import transcribe_after_response


@dataclass(frozen=True)
class AuthenticatedUser:
    uid: str
    email: str | None
    display_name: str | None = None
    picture: str | None = None
    #: True for demo accounts: reads are allowed, every write is rejected by the API.
    read_only: bool = False


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
    return UserService(
        get_firestore_client(),
        storage=get_storage_client(),
        # Account deletion revokes the connected accounts' OAuth grants before dropping the tree.
        connections=get_connection_service(),
    )


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
        content=get_channel_content_service(),
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
    return GlossaryService(client, projects=ProjectService(client, storage=get_storage_client()))


def get_connection_service() -> ConnectionService:
    settings = get_settings()
    return ConnectionService(
        get_firestore_client(),
        cipher=get_token_cipher(),
        settings=settings,
    )


def get_creator_library_service() -> CreatorLibraryService:
    client = get_firestore_client()
    storage = get_storage_client()
    return CreatorLibraryService(
        client,
        storage=storage,
        imports=CreatorImportService(client, storage=storage),
        connections=get_connection_service(),
        embeddings=get_providers().embeddings,
        settings=get_settings(),
    )


def get_channel_content_service() -> ChannelContentService:
    return ChannelContentService(
        get_firestore_client(),
        connections=get_connection_service(),
        imports=CreatorImportService(get_firestore_client(), storage=get_storage_client()),
        library=get_creator_library_service(),
        settings=get_settings(),
    )


@lru_cache
def get_token_cipher() -> TokenCipher:
    return build_token_cipher(get_settings())


def get_publish_service() -> PublishService:
    client = get_firestore_client()
    storage = get_storage_client()
    settings = get_settings()
    projects = ProjectService(client, storage=storage)
    jobs = JobService(client)
    transcripts = TranscriptService(client, storage=storage)
    return PublishService(
        client,
        projects=projects,
        jobs=jobs,
        connections=get_connection_service(),
        assets=AssetService(
            client, projects=projects, jobs=jobs, storage=storage, settings=settings
        ),
        captions=CaptionRenderService(
            client,
            projects=projects,
            jobs=jobs,
            transcripts=transcripts,
            storage=storage,
            url_ttl_seconds=settings.upload_url_ttl_seconds,
        ),
        localizations=get_localization_service(),
        transcripts=transcripts,
        thumbnails=ThumbnailService(
            client,
            projects=projects,
            jobs=jobs,
            storage=storage,
            url_ttl_seconds=settings.upload_url_ttl_seconds,
            price_per_image_usd=settings.imagegen_price_per_image_usd,
            max_project_cost_usd=settings.max_project_cost_usd,
        ),
        storage=storage,
        settings=settings,
    )


# (background_tasks, *, owner_uid, project_id, job_id) -> None. Injected so tests can
# record scheduling without running the worker.
PublishScheduler = Callable[..., None]


def get_publish_scheduler() -> PublishScheduler:
    return publish_after_response


def get_schedule_service() -> ScheduleService:
    client = get_firestore_client()
    return ScheduleService(client, projects=ProjectService(client))


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


def get_persona_research_service() -> PersonaResearchService:
    return PersonaResearchService(
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

BearerCredentials = Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)]


def current_user(request: Request, credentials: BearerCredentials) -> AuthenticatedUser:
    if credentials is None or not credentials.credentials:
        raise HTTPException(status_code=401, detail="Missing bearer token")
    # The read-only middleware may already have verified this token for a mutating request;
    # reuse its result instead of verifying twice.
    decoded = getattr(request.state, "firebase_token_claims", None)
    if decoded is None:
        try:
            decoded = verify_id_token(credentials.credentials)
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(status_code=401, detail="Invalid token") from exc
        request.state.firebase_token_claims = decoded
    uid = decoded["uid"]
    return AuthenticatedUser(
        uid=uid,
        email=decoded.get("email"),
        display_name=decoded.get("name"),
        picture=decoded.get("picture"),
        read_only=uid in set(get_settings().read_only_user_uids),
    )
