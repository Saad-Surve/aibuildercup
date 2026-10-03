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
    #: Draft studio writing partner (Gemini). Defaults to the flash-lite tier; the
    #: deployed config can point it at a stronger Gemini for better prose.
    model_writer: str = "gemini-3.1-flash-lite"
    #: Images use Gemini image generation ("Nano Banana") on Agent Platform. It accepts
    #: reference images (the creator's real face), edits conversationally, and renders
    #: legible text, unlike Imagen. See docs/current-progress/2026-10-03-1015.
    model_image: str = "gemini-3.1-flash-image"
    #: Higher-fidelity image model for hero shots; more expensive. Used only when a
    #: request explicitly opts into it.
    model_image_pro: str = "gemini-3-pro-image"
    #: Localization cultural-adaptation pass (the second translation stage). Flash-lite
    #: keeps a long transcript cheap; point it at a stronger Gemini for better prose.
    model_localization: str = "gemini-3.1-flash-lite"
    model_video: str = "veo-3.1-fast"
    model_stt: str = "chirp_3"

    # Thumbnail studio. `imagegen_max_concepts` bounds one generation batch, and the
    # per-image price feeds the project cost guard. Fetching real frames as references is
    # what keeps the creator's likeness; `thumbnail_reference_frames` caps how many are
    # attached per image so a call cannot balloon.
    imagegen_max_concepts: int = 4
    imagegen_default_aspect: str = "16:9"
    imagegen_default_size: str = "1K"
    imagegen_price_per_image_usd: float = 0.067
    thumbnail_reference_frames: int = 3
    thumbnail_frame_max_width: int = 1024

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

    # Caption burn-in: sources up to this size are downloaded to the worker's temp dir before
    # encoding. Local files probe reliably (fragmented MP4s otherwise make a remote ffprobe
    # scan the whole object) and seek faster; larger sources are streamed from a signed URL
    # instead so the temp disk cannot fill up.
    caption_max_source_download_bytes: int = 300_000_000

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

    # Dubbing / localization. Text-to-Speech renders each transcript segment and the worker
    # duration-normalizes it into the segment's window before muxing. The sample rate is the
    # rate the whole dubbed track is assembled at, so it must be one Cloud TTS accepts. The
    # voice catalog lives in `app/services/dubbing.py`; `dub_default_voice` is only a fallback
    # when a request omits `voice`.
    tts_sample_rate_hz: int = 24000
    dub_default_voice: str = "en-US-Neural2-D"
    #: Mix the source audio quietly under the dub instead of replacing it. Overridable per
    #: request with `keepOriginalAudio`.
    dub_keep_original_audio: bool = False
    #: `atempo` bends pitch-preserving tempo within [0.5, 2.0]; values past the clamp mean the
    #: take cannot fit the window and is truncated (compressed takes) or padded (expanded ones).
    dub_min_tempo: float = 0.75
    dub_max_tempo: float = 1.5
    dub_original_audio_volume: float = 0.12
    #: How many Text-to-Speech calls run at once. Bounded so a long transcript does not
    #: trip the Text-to-Speech per-minute quota or hold a huge number of connections.
    dub_max_concurrency: int = 4
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
