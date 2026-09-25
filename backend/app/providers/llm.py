"""LLM provider.

Thin wrapper over the Gemini Developer API (AI Studio). Feature code calls this provider,
never `google.genai` directly.
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

    async def _real(
        self,
        *,
        model: str,
        system: str,
        user: str,
        schema: dict[str, Any],
    ) -> LlmCompletion:
        from google import genai
        from google.genai import errors as genai_errors

        if not self.settings.gemini_api_key:
            raise RuntimeError(
                "GEMINI_API_KEY is not set. The LLM provider only uses the Gemini Developer "
                "API (AI Studio); create a key at https://aistudio.google.com/apikey and set "
                "GEMINI_API_KEY."
            )
        logger.info("LLM call via Gemini Developer API (%s)", model)
        client = genai.Client(api_key=self.settings.gemini_api_key)

        attempts = max(1, self.settings.llm_max_attempts)
        result = None
        for attempt in range(1, attempts + 1):
            try:
                result = client.models.generate_content(
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
                    "Gemini returned %s (%s); retry %d/%d in %.1fs",
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
