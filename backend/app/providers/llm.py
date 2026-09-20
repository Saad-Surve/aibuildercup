"""LLM provider with cassette support.

In `on`/`auto` mode a cassette hit is replayed. In `auto`, a miss calls the real service once and
records the response. In `off`, always real.
"""

import asyncio
import json
import logging
from typing import Any

from app.config import Settings
from app.providers.cassette import CassetteStore

logger = logging.getLogger(__name__)

# Statuses worth retrying: the model was overloaded, rate-limited, or a transient server error.
TRANSIENT_STATUS_CODES = frozenset({429, 500, 502, 503, 504})


class CassetteMiss(RuntimeError):
    def __init__(self, key: str) -> None:
        super().__init__(f"No cassette for key {key} in MOCK_MODE=on")
        self.key = key


class LlmProvider:
    provider_name = "llm"

    def __init__(self, settings: Settings, cassettes: CassetteStore) -> None:
        self.settings = settings
        self.cassettes = cassettes

    async def complete_json(
        self,
        *,
        model: str,
        prompt_version: str,
        system: str,
        user: str,
        schema: dict[str, Any],
    ) -> dict[str, Any]:
        request = {"system": system, "user": user, "schema": schema}
        key = CassetteStore.make_key(self.provider_name, model, prompt_version, request)

        if self.settings.mock_mode in ("on", "auto"):
            hit = self.cassettes.load(self.provider_name, key)
            if hit is not None:
                return hit["response"]
            if self.settings.mock_mode == "on":
                raise CassetteMiss(key)

        response = await self._real(
            model=model, system=system, user=user, schema=schema
        )

        # Only `auto` records. `off` is always-real with no cassette side effects, which also
        # keeps production from trying to write into a non-existent fixtures directory.
        if self.settings.mock_mode == "auto":
            self.cassettes.save(
                self.provider_name,
                key,
                model=model,
                prompt_version=prompt_version,
                request_summary=f"{prompt_version} ({model})",
                response=response,
            )
        return response

    async def _real(
        self,
        *,
        model: str,
        system: str,
        user: str,
        schema: dict[str, Any],
    ) -> dict[str, Any]:
        from google import genai
        from google.genai import errors as genai_errors

        if not self.settings.gemini_api_key:
            raise RuntimeError(
                "GEMINI_API_KEY is not set. The LLM provider only uses the Gemini Developer "
                "API (AI Studio); create a key at https://aistudio.google.com/apikey and set "
                "GEMINI_API_KEY, or run with MOCK_MODE=on to use cassettes/templates."
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
        return json.loads(text)
