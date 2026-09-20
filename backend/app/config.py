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

    # Model registry. Agents never hardcode model ids; they read these.
    model_reviewer: str = "gemini-2.5-flash"
    model_orchestrator: str = "gemini-2.5-pro"
    model_image: str = "imagen-4.0-generate-001"
    model_video: str = "veo-3.1-fast"
    model_stt: str = "chirp_3"

    max_reviewer_concurrency: int = 4
    max_project_cost_usd: float = 5.0

    @property
    def is_local(self) -> bool:
        return self.environment == "local"


@lru_cache
def get_settings() -> Settings:
    return Settings()
