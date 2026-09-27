"""LLM provider.

Thin wrapper over Gemini on Agent Platform (Vertex AI), authenticated with Application Default
Credentials against `settings.project_id` / `settings.vertex_location`. Feature code calls this
provider, never `google.genai` directly.

Two entry points:

- `complete_json`: one structured call (optionally with inline media).
- `complete_json_with_tools`: a function-calling loop. The model may call the supplied tools;
  each call is executed and its returned media is attached to the function response so the model
  can *see* it before it answers. Used by the reviewers to pull a frame or clip mid-review.
"""

import asyncio
import json
import logging
from collections.abc import Sequence
from typing import Any

from app.config import Settings
from app.providers.base import (
    LlmCompletion,
    LlmUsage,
    MediaPart,
    ToolCall,
    ToolExecutor,
    ToolSpec,
)

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
        media: Sequence[MediaPart] = (),
    ) -> LlmCompletion:
        del prompt_version  # Part of the provider interface; unused by the live call.
        from google.genai import types

        contents = [_user_content(types, user, media)]
        result = await self._generate(
            model=model, contents=contents, system=system, schema=schema, tools=None
        )
        return _completion_from(result)

    async def complete_json_with_tools(
        self,
        *,
        model: str,
        prompt_version: str,
        system: str,
        user: str,
        schema: dict[str, Any],
        tools: Sequence[ToolSpec],
        execute: ToolExecutor,
        media: Sequence[MediaPart] = (),
        max_tool_rounds: int = 2,
        max_tool_calls: int = 4,
    ) -> LlmCompletion:
        del prompt_version
        from google.genai import types

        contents: list[Any] = [_user_content(types, user, media)]
        declarations = _function_declarations(types, tools)
        calls: list[ToolCall] = []
        usage = LlmUsage()
        calls_made = 0
        result = None

        for round_index in range(max(0, max_tool_rounds) + 1):
            tools_allowed = round_index < max_tool_rounds and calls_made < max_tool_calls
            result = await self._generate(
                model=model,
                contents=contents,
                system=system,
                schema=schema,
                tools=declarations if tools_allowed else None,
            )
            usage = _add_usage(usage, _usage_from(result))
            function_calls = list(result.function_calls or [])
            if not tools_allowed or not function_calls:
                break
            content = result.candidates[0].content if result.candidates else None
            if content is None:  # pragma: no cover - safety/finish without content
                break
            contents.append(content)

            response_parts: list[Any] = []
            for function_call in function_calls:
                name = function_call.name or ""
                arguments = dict(function_call.args or {})
                if calls_made >= max_tool_calls:
                    response_parts.append(
                        types.Part.from_function_response(
                            name=name,
                            response={"status": "error", "detail": "tool budget reached"},
                        )
                    )
                    continue
                calls_made += 1
                try:
                    returned = list(await execute(name, arguments))
                except Exception as exc:  # noqa: BLE001 - a failed tool must not sink the review
                    logger.warning("LLM tool %s failed: %s", name, exc)
                    calls.append(
                        ToolCall(name=name, arguments=arguments, ok=False, error=str(exc)[:300])
                    )
                    response_parts.append(
                        types.Part.from_function_response(
                            name=name, response={"status": "error", "detail": str(exc)[:200]}
                        )
                    )
                    continue
                calls.append(
                    ToolCall(name=name, arguments=arguments, media=tuple(returned), ok=True)
                )
                response_parts.append(
                    types.Part.from_function_response(
                        name=name,
                        response={"status": "ok", "attachments": len(returned)},
                        parts=[
                            types.FunctionResponsePart.from_bytes(
                                data=item.data, mime_type=item.mime_type
                            )
                            for item in returned
                        ],
                    )
                )
            contents.append(types.Content(role="user", parts=response_parts))

        if result is None:  # pragma: no cover - loop always runs at least once
            raise RuntimeError("LLM tool loop produced no result")
        completion = _completion_from(result)
        return LlmCompletion(
            data=completion.data, usage=usage, tool_calls=tuple(calls)
        )

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

    async def _generate(
        self,
        *,
        model: str,
        contents: Any,
        system: str,
        schema: dict[str, Any],
        tools: list[Any] | None,
    ) -> Any:
        """One `generate_content` call, retrying transient failures."""
        from google.genai import errors as genai_errors

        client = self._client()
        logger.info(
            "LLM call model=%s tools=%s", model, len(tools) if tools else 0
        )
        config: dict[str, Any] = {
            "system_instruction": system,
            "response_mime_type": "application/json",
            "response_schema": schema,
        }
        if tools:
            # Declarations only: we execute the calls ourselves (plain `generate_content`
            # cannot run SDK automatic function calling), so it is disabled explicitly.
            config["tools"] = [_tool(tools)]
            config["automatic_function_calling"] = {"disable": True}

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
                    contents=contents,
                    config=config,
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
        return result


def _tool(declarations: list[Any]) -> Any:
    from google.genai import types

    return types.Tool(function_declarations=declarations)


def _user_content(types: Any, user: str, media: Sequence[MediaPart]) -> Any:
    parts: list[Any] = [types.Part.from_text(text=user)]
    for item in media:
        if item.label:
            parts.append(types.Part.from_text(text=item.label))
        parts.append(types.Part.from_bytes(data=item.data, mime_type=item.mime_type))
    return types.Content(role="user", parts=parts)


def _function_declarations(types: Any, specs: Sequence[ToolSpec]) -> list[Any]:
    return [
        types.FunctionDeclaration(
            name=spec.name,
            description=spec.description,
            parameters_json_schema=spec.parameters,
        )
        for spec in specs
    ]


def _completion_from(result: Any) -> LlmCompletion:
    text = result.text
    if text is None:
        raise RuntimeError("LLM returned an empty response")
    return LlmCompletion(data=json.loads(text), usage=_usage_from(result))


def _add_usage(left: LlmUsage, right: LlmUsage) -> LlmUsage:
    return LlmUsage(
        input_tokens=left.input_tokens + right.input_tokens,
        output_tokens=left.output_tokens + right.output_tokens,
    )


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
