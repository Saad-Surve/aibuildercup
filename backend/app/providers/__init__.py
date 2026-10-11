from functools import lru_cache

from app.config import Settings, get_settings
from app.providers.embeddings import GeminiEmbeddingProvider
from app.providers.imagegen import ImageGenProvider
from app.providers.llm import LlmProvider
from app.providers.stt import SttProvider
from app.providers.translate import TranslateProvider
from app.providers.tts import TtsProvider
from app.providers.videogen import VideoGenProvider


class Providers:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.embeddings = GeminiEmbeddingProvider(settings)
        self.llm = LlmProvider(settings)
        self.images = ImageGenProvider(settings)
        self.stt = SttProvider(settings)
        self.tts = TtsProvider(settings)
        self.translate = TranslateProvider(settings)
        self.videos = VideoGenProvider(settings)


def build_providers(settings: Settings) -> Providers:
    return Providers(settings)


@lru_cache
def get_providers() -> Providers:
    return build_providers(get_settings())


__all__ = ["Providers", "build_providers", "get_providers"]
