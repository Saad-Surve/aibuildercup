from functools import lru_cache

from app.config import Settings, get_settings
from app.providers.llm import LlmProvider
from app.providers.stt import SttProvider


class Providers:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.llm = LlmProvider(settings)
        self.stt = SttProvider(settings)


def build_providers(settings: Settings) -> Providers:
    return Providers(settings)


@lru_cache
def get_providers() -> Providers:
    return build_providers(get_settings())
