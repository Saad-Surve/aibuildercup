"""LLM provider with cassette support.

In `on`/`auto` mode a cassette hit is replayed. In `auto`, a miss calls the real service once and
records the response. In `off`, always real.
"""

from typing import Any

from app.config import Settings
from app.providers.cassette import CassetteStore


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

        client = genai.Client(
            vertexai=True, project=self.settings.project_id, location=self.settings.region
        )
        result = client.models.generate_content(
            model=model,
            contents=user,
            config={
                "system_instruction": system,
                "response_mime_type": "application/json",
                "response_schema": schema,
            },
        )
        import json

        text = result.text
        if text is None:
            raise RuntimeError("LLM returned an empty response")
        return json.loads(text)
