"""Translation provider.

Thin wrapper over Cloud Translation (Advanced, v3). Feature code calls this provider, never
`google.cloud.translate_v3` directly. It is a plain text-to-text pass; the cultural-adaptation
step the design describes is a separate, later concern and is not wired here.

Authentication is Application Default Credentials, same as every other provider.
"""

import logging
from typing import Any

from app.config import Settings

logger = logging.getLogger(__name__)


def base_language(code: str | None) -> str | None:
    """Cloud Translation wants a base code (`en`), not a region variant (`en-US`)."""
    if not code:
        return None
    return code.replace("_", "-").split("-", 1)[0].lower()


class TranslateProvider:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._cached_client: object | None = None

    async def translate(
        self,
        *,
        texts: list[str],
        target_language: str,
        source_language: str | None,
        glossary_id: str | None,
    ) -> list[str]:
        if not texts:
            return []
        source = base_language(source_language)
        target = base_language(target_language)
        if source and target and source == target:
            # Nothing to translate; the caller still gets a same-length result.
            return list(texts)
        return await self._real(
            texts=texts,
            target_language=target or target_language,
            source_language=source,
            glossary_id=glossary_id,
        )

    async def _real(
        self,
        *,
        texts: list[str],
        target_language: str,
        source_language: str | None,
        glossary_id: str | None,
    ) -> list[str]:
        import asyncio

        from google.cloud import translate_v3 as translate

        client = self._client(translate)
        parent = (
            f"projects/{self.settings.project_id}/locations/{self.settings.region}"
        )
        request = translate.TranslateTextRequest(
            parent=parent,
            contents=list(texts),
            mime_type="text/plain",
            target_language_code=target_language,
            source_language_code=source_language or None,
        )
        logger.info(
            "Translation call target=%s source=%s lines=%d",
            target_language,
            source_language,
            len(texts),
        )
        response = await asyncio.to_thread(client.translate_text, request=request)
        translated = [t.translated_text for t in response.translations]
        if len(translated) != len(texts):
            raise RuntimeError(
                "Translation returned a different number of lines than it was given"
            )
        return translated

    def _client(self, translate: Any) -> Any:
        if self._cached_client is None:
            self._cached_client = translate.TranslationServiceClient()
        return self._cached_client
