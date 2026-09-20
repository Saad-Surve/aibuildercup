from functools import lru_cache

from app.config import Settings, get_settings
from app.providers.cassette import CassetteStore
from app.providers.llm import LlmProvider


class Providers:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.cassettes = CassetteStore(settings.cassette_dir)
        self.llm = LlmProvider(settings, self.cassettes)


def build_providers(settings: Settings) -> Providers:
    return Providers(settings)


@lru_cache
def get_providers() -> Providers:
    return build_providers(get_settings())
