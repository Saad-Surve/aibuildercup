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

    # Agent Platform (Vertex AI) location. "global" is the cheapest Gemini endpoint and is not
    # tied to the default `region`. Every LLM call goes through Agent Platform using Application
    # Default Credentials: locally via `gcloud auth application-default login`, on Cloud Run via
    # the runtime service account.
    vertex_location: str = "global"

    # Retry transient Gemini failures (429/5xx) with exponential backoff before giving up.
    llm_max_attempts: int = 4
    llm_retry_base_seconds: float = 0.5

    # Model registry. Agents never hardcode model ids; they read these. Two configurations:
    #   - local (`backend/.env.example`): the cheap `gemini-3.1-flash-lite` tier.
    #   - deployed (`backend/.env.deploy.example`): the stronger `gemini-3.8-flash`.
    # Both run on Agent Platform (Vertex AI) with `response_mime_type`/`response_schema`
    # controlled generation. Pin a concrete id if you need reproducibility.
    model_reviewer: str = "gemini-3.1-flash-lite"
    model_orchestrator: str = "gemini-3.1-flash-lite"
    model_transcript_repair: str = "gemini-3.1-flash-lite"
    model_image: str = "imagen-4.0-generate-001"
    model_video: str = "veo-3.1-fast"
    model_stt: str = "chirp_3"

    # Transcript cleanup: after Chirp returns, one cheap LLM pass fixes only obvious
    # recognition errors and infers speaker turns. Best-effort; a failure keeps the raw
    # transcript. Disable to compare raw STT output.
    transcript_repair_enabled: bool = True
    transcript_repair_max_chars: int = 12_000

    # Reviewer footage tools (FFmpeg). When on, a reviewer may call extract_frame /
    # cut_clip during its own review, then grade with the footage attached. Bounded per
    # reviewer call: `max_visual_context_requests` is the total tool calls, and
    # `visual_tool_max_rounds` is how many tool round-trips are allowed.
    review_visual_tools_enabled: bool = True
    max_visual_context_requests: int = 3
    visual_tool_max_rounds: int = 2
    visual_clip_window_seconds: int = 5
    ffmpeg_path: str = "ffmpeg"
    #: ffprobe is used to read the true media duration so corrupt STT timestamps can be
    #: dropped (Chirp occasionally emits words past the end of the video).
    ffprobe_path: str = "ffprobe"

    # Truth reviewer: verify hard claims against Google Search instead of model memory.
    # Gemini 3 only; billed per search query after 5k free/month, so only the truth
    # reviewer opts in (see `TruthEvidenceReviewer.supports_grounding`).
    truth_grounding_enabled: bool = True

    # Speech-to-Text location. Chirp 3 (multilingual, language-agnostic transcription) is GA on
    # the `us` multi-region but not in `us-central1`, so STT is the one service that does not use
    # the default region.
    stt_region: str = "us"
    # STT V2 cannot auto-detect AAC inside video containers (MP4/MOV/M4A), so those need an
    # explicit decoding config with a sample rate and channel count. Defaults match creator /
    # social video (44.1 kHz stereo).
    stt_sample_rate_hz: int = 44100
    stt_audio_channel_count: int = 2
    # Speaker diarization. When enabled, the worker asks STT to label each word with a speaker
    # index (Chirp 3 assigns `speaker_label`), segments split on speaker changes, and the UI
    # shows the turns. Behind a flag so a model/region that rejects the feature can be switched
    # off with an env var instead of a code change.
    stt_enable_diarization: bool = True

    # Pub/Sub push verification. When `pubsub_push_audience` is set, the internal push endpoint
    # requires a valid Google OIDC token for this audience (the Cloud Run URL) minted by
    # `pubsub_push_service_account`. Left blank locally, where the endpoint is not public.
    pubsub_push_audience: str | None = None
    pubsub_push_service_account: str | None = None

    max_reviewer_concurrency: int = 4
    max_project_cost_usd: float = 5.0

    # LLM prices in USD per 1M tokens, used to turn reported token usage into `costEstimateUsd`.
    # These default to the local flash-lite tier; the deployed config overrides them for
    # gemini-3.8-flash (0.75 / 3.75 through 2026-12-31, then 1.50 / 7.50). They are not
    # auto-detected from the model id.
    # Source: https://cloud.google.com/gemini-enterprise-agent-platform/generative-ai/pricing
    llm_input_price_per_mtok: float = 0.25
    llm_output_price_per_mtok: float = 1.50

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
