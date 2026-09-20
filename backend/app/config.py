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

    max_reviewer_concurrency: int = 4
    max_project_cost_usd: float = 5.0

    @property
    def is_local(self) -> bool:
        return self.environment == "local"


@lru_cache
def get_settings() -> Settings:
    return Settings()
