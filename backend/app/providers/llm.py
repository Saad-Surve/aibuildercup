"""LLM provider.

Thin wrapper over two Google LLM backends, selected by `settings.llm_backend`:

- "developer": the Gemini Developer API (AI Studio), authenticated with `GEMINI_API_KEY`.
  Free tier — the default so local runs use free Gemma models and never spend GCP budget.
- "vertex": Gemini Enterprise Agent Platform (formerly Vertex AI), authenticated with
  Application Default Credentials against the project/location. Billable, deployed only.

Feature code calls this provider, never `google.genai` directly.
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

    def _client(self) -> Any:
        """Build the GenAI client for the configured backend.

        Lazy imports keep `google.genai` out of the module import path (and out of tests that
        never touch the network).
        """
        from google import genai

        if self.settings.llm_backend == "vertex":
            logger.info(
                "LLM via Agent Platform (vertex) project=%s location=%s",
                self.settings.project_id,
                self.settings.vertex_location,
            )
            return genai.Client(
                vertexai=True,
                project=self.settings.project_id,
                location=self.settings.vertex_location,
            )

        if not self.settings.gemini_api_key:
            raise RuntimeError(
                "GEMINI_API_KEY is not set for the 'developer' LLM backend. Create a key at "
                "https://aistudio.google.com/apikey, set GEMINI_API_KEY, or set LLM_BACKEND=vertex "
                "to use Agent Platform with Application Default Credentials."
            )
        return genai.Client(api_key=self.settings.gemini_api_key)

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
        logger.info("LLM call (%s) model=%s", self.settings.llm_backend, model)

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
                    "LLM backend %s returned %s (%s); retry %d/%d in %.1fs",
                    self.settings.llm_backend,
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
