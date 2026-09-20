"""Provider interfaces.

Nothing in the app imports a Google SDK directly. Everything goes through one of these
interfaces, which has a real implementation and a cassette implementation. That is what makes
the mock layer possible without conditionals scattered everywhere.
"""

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class LlmProvider(Protocol):
    async def complete_json(
        self,
        *,
        model: str,
        prompt_version: str,
        system: str,
        user: str,
        schema: dict[str, Any],
    ) -> dict[str, Any]: ...


@runtime_checkable
class SttProvider(Protocol):
    async def transcribe(
        self,
        *,
        gcs_uri: str,
        language: str,
        model: str,
    ) -> dict[str, Any]: ...


@runtime_checkable
class TranslateProvider(Protocol):
    async def translate(
        self,
        *,
        texts: list[str],
        target_language: str,
        source_language: str | None,
        glossary_id: str | None,
    ) -> list[str]: ...


@runtime_checkable
class TtsProvider(Protocol):
    async def synthesize(
        self,
        *,
        text: str,
        language: str,
        voice: str,
    ) -> bytes: ...


@runtime_checkable
class ImageGenProvider(Protocol):
    async def generate(
        self,
        *,
        model: str,
        prompt: str,
        count: int,
    ) -> list[bytes]: ...


@runtime_checkable
class VideoGenProvider(Protocol):
    async def generate(
        self,
        *,
        model: str,
        prompt: str,
        duration_seconds: int,
        aspect_ratio: str,
    ) -> str: ...


@runtime_checkable
class SocialProvider(Protocol):
    async def fetch_posts(self, connection: dict[str, Any]) -> list[dict[str, Any]]: ...

    async def fetch_metrics(
        self, connection: dict[str, Any], date_range: dict[str, str]
    ) -> list[dict[str, Any]]: ...

    async def fetch_comments(self, connection: dict[str, Any]) -> list[dict[str, Any]]: ...
