"""LLM provider.

Thin wrapper over Gemini on Agent Platform (Vertex AI), authenticated with Application Default
Credentials against `settings.project_id` / `settings.vertex_location`. Feature code calls this
provider, never `google.genai` directly.
"""

import asyncio
import json
import logging
from typing import Any

from app.config import Settings
from app.providers.base import LlmCompletion, LlmUsage

logger = logging.getLogger(__name__)

# Statuses worth retrying: the model was overloaded, rate-limited, or a transient server error.
TRANSIENT_STATUS_CODES = frozenset({429, 500, 502, 503, 504})


class LlmProvider:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        # Built once and reused: constructing a client is not free, and the
        # worker calls this per reviewer.
        self._cached_client: Any | None = None

    async def complete_json(
        self,
        *,
        model: str,
        prompt_version: str,
        system: str,
        user: str,
        schema: dict[str, Any],
    ) -> LlmCompletion:
        del prompt_version  # Part of the provider interface; unused by the live call.
        return await self._real(model=model, system=system, user=user, schema=schema)

    def _client(self) -> Any:
        """Build (once) the Agent Platform client.

        A lazy import keeps `google.genai` out of the module import path. No API
        key: ADC supplies credentials.
        """
        if self._cached_client is None:
            from google import genai

            logger.info(
                "LLM via Agent Platform project=%s location=%s",
                self.settings.project_id,
                self.settings.vertex_location,
            )
            self._cached_client = genai.Client(
                vertexai=True,
                project=self.settings.project_id,
                location=self.settings.vertex_location,
            )
        return self._cached_client

    async def _real(
        self,
        *,
        model: str,
        system: str,
        user: str,
        schema: dict[str, Any],
    ) -> LlmCompletion:
        from google.genai import errors as genai_errors

        client = self._client()
        logger.info("LLM call model=%s", model)

        attempts = max(1, self.settings.llm_max_attempts)
        result = None
        for attempt in range(1, attempts + 1):
            try:
                # `generate_content` is synchronous and takes seconds. Calling it
                # directly inside this coroutine blocks the event loop, which
                # starves the realtime websocket and every other request on the
                # instance (this is a single-instance service). Off-loop it goes.
                result = await asyncio.to_thread(
                    client.models.generate_content,
                    model=model,
                    contents=user,
                    config={
                        "system_instruction": system,
                        "response_mime_type": "application/json",
                        "response_schema": schema,
                    },
                )
                break
            except genai_errors.APIError as exc:
                code = getattr(exc, "code", None)
                if code not in TRANSIENT_STATUS_CODES or attempt == attempts:
                    raise
                delay = self.settings.llm_retry_base_seconds * (2 ** (attempt - 1))
                logger.warning(
                    "LLM returned %s (%s); retry %d/%d in %.1fs",
                    code,
                    getattr(exc, "status", ""),
                    attempt,
                    attempts,
                    delay,
                )
                await asyncio.sleep(delay)

        if result is None:  # pragma: no cover - loop always returns or raises
            raise RuntimeError("LLM call produced no result")
        text = result.text
        if text is None:
            raise RuntimeError("LLM returned an empty response")
        return LlmCompletion(data=json.loads(text), usage=_usage_from(result))


def _usage_from(result: Any) -> LlmUsage:
    """Read `usage_metadata` off a generate_content result.

    Thinking tokens are billed as output, so they are added to the output count.
    Anything missing is reported as zero rather than guessed.
    """
    metadata = getattr(result, "usage_metadata", None)
    if metadata is None:
        return LlmUsage()
    prompt = getattr(metadata, "prompt_token_count", None) or 0
    candidates = getattr(metadata, "candidates_token_count", None) or 0
    thoughts = getattr(metadata, "thoughts_token_count", None) or 0
    return LlmUsage(input_tokens=int(prompt), output_tokens=int(candidates + thoughts))
