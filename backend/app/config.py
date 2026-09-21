from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    environment: str = "local"
    project_id: str = "habeas-codus"
    region: str = "us-central1"

    # off  = always call the real service
    # auto = replay a cassette on hit, call real once and record on miss
    # on   = cassette only, never touch the network
    mock_mode: Literal["off", "auto", "on"] = "auto"
    cassette_dir: str = "../fixtures/cassettes"

    firebase_project_id: str = "habeas-codus"
    media_bucket: str = "habeas-codus-media"
    corpus_bucket: str = "habeas-codus-corpus"

    # Browser origins allowed to call this API. Override with a JSON array in CORS_ALLOWED_ORIGINS.
    cors_allowed_origins: list[str] = [
        "http://localhost:3000",
        "http://localhost:8080",
        "https://habeas-codus.web.app",
        "https://habeas-codus.firebaseapp.com",
    ]

    # Gemini Developer API (AI Studio) key. This is the only LLM backend: there is no Vertex AI
    # path. Required for any real (non-cassette) LLM call. Get one at
    # https://aistudio.google.com/apikey
    gemini_api_key: str | None = None

    # Retry transient Gemini failures (429/5xx) with exponential backoff before giving up.
    llm_max_attempts: int = 4
    llm_retry_base_seconds: float = 0.5

    # Model registry. Agents never hardcode model ids; they read these. Gemini 2.5 models are
    # retired for new AI Studio keys and `gemini-*-pro` is not on the free tier, so default to the
    # rolling flash alias. Pin a concrete id (e.g. gemini-3.6-flash) if you need reproducibility.
    model_reviewer: str = "gemini-flash-latest"
    model_orchestrator: str = "gemini-flash-latest"
    model_image: str = "imagen-4.0-generate-001"
    model_video: str = "veo-3.1-fast"
    model_stt: str = "chirp_3"

    max_reviewer_concurrency: int = 4
    max_project_cost_usd: float = 5.0

    # Local development: plain user ADC has no service-account identity, so signed URLs are
    # minted for this service account through IAM signBlob (the caller needs
    # roles/iam.serviceAccountTokenCreator on it). Defaults to the Cloud Run runtime SA.
    storage_signing_service_account: str | None = None

    # Upload limits. `max_upload_size_bytes` mirrors users/{uid}.limits.maxVideoSizeBytes.
    max_upload_size_bytes: int = 524_288_000
    upload_url_ttl_seconds: int = 900

    @property
    def is_local(self) -> bool:
        return self.environment == "local"


@lru_cache
def get_settings() -> Settings:
    return Settings()
