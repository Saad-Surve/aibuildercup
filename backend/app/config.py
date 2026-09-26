from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    environment: str = "local"
    project_id: str = "habeas-codus"
    region: str = "us-central1"

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
    # path. Required for every LLM call. Get one at
    # https://aistudio.google.com/apikey
    gemini_api_key: str | None = None

    # Retry transient Gemini failures (429/5xx) with exponential backoff before giving up.
    llm_max_attempts: int = 4
    llm_retry_base_seconds: float = 0.5

    # Model registry. Agents never hardcode model ids; they read these. Defaults to Gemma 4
    # (`gemma-4-26b-a4b-it`), hosted on the Gemini Developer API: it is free, has a far more
    # generous free-tier request quota than the Gemini flash models, and accepts the same
    # `response_mime_type`/`response_schema` controlled-generation config the provider sends.
    # Set these back to `gemini-flash-latest` for the stronger Gemini flash-class quality. Pin a
    # concrete id (e.g. gemma-4-31b-it) if you need reproducibility.
    model_reviewer: str = "gemma-4-26b-a4b-it"
    model_orchestrator: str = "gemma-4-26b-a4b-it"
    model_image: str = "imagen-4.0-generate-001"
    model_video: str = "veo-3.1-fast"
    model_stt: str = "chirp_3"

    # Speech-to-Text location. Chirp 3 (multilingual, language-agnostic transcription) is GA on
    # the `us` multi-region but not in `us-central1`, so STT is the one service that does not use
    # the default region.
    stt_region: str = "us"
    # STT V2 cannot auto-detect AAC inside video containers (MP4/MOV/M4A), so those need an
    # explicit decoding config with a sample rate and channel count. Defaults match creator /
    # social video (44.1 kHz stereo).
    stt_sample_rate_hz: int = 44100
    stt_audio_channel_count: int = 2

    # Pub/Sub push verification. When `pubsub_push_audience` is set, the internal push endpoint
    # requires a valid Google OIDC token for this audience (the Cloud Run URL) minted by
    # `pubsub_push_service_account`. Left blank locally, where the endpoint is not public.
    pubsub_push_audience: str | None = None
    pubsub_push_service_account: str | None = None

    max_reviewer_concurrency: int = 4
    max_project_cost_usd: float = 5.0

    # LLM prices in USD per 1M tokens, used to turn reported token usage into `costEstimateUsd`.
    # The default model registry above is Gemma 4, which is free, so these default to zero. If you
    # move the registry back to a Gemini model, override them here (Gemini flash-class is
    # ~$0.75 in / $3.75 out); they are not auto-detected from the model id.
    # Source: https://ai.google.dev/gemini-api/docs/pricing
    llm_input_price_per_mtok: float = 0.0
    llm_output_price_per_mtok: float = 0.0

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
