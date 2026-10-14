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
    GroundingInfo,
    GroundingSource,
    LlmCompletion,
    LlmUsage,
    MediaPart,
    ToolCall,
    ToolExecutor,
    ToolSpec,
)
from app.providers.gemini_client import get_gemini_client

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
        media: Sequence[MediaPart] = (),
        grounding: bool = False,
        temperature: float | None = None,
        max_attempts: int | None = None,
        max_output_tokens: int | None = None,
        thinking_level: str | None = None,
    ) -> LlmCompletion:
        del prompt_version  # Part of the provider interface; unused by the live call.
        from google.genai import types

        contents = [_user_content(types, user, media)]
        result = await self._generate(
            model=model,
            contents=contents,
            system=system,
            schema=schema,
            function_declarations=None,
            grounding=grounding,
            temperature=temperature,
            max_attempts=max_attempts,
            max_output_tokens=max_output_tokens,
            thinking_level=thinking_level,
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
        grounding: bool = False,
    ) -> LlmCompletion:
        del prompt_version
        from google.genai import types

        contents: list[Any] = [_user_content(types, user, media)]
        declarations = _function_declarations(types, tools)
        calls: list[ToolCall] = []
        usage = LlmUsage()
        searched = GroundingInfo()
        calls_made = 0
        result = None

        for round_index in range(max(0, max_tool_rounds) + 1):
            tools_allowed = round_index < max_tool_rounds and calls_made < max_tool_calls
            result = await self._generate(
                model=model,
                contents=contents,
                system=system,
                schema=schema,
                function_declarations=declarations if tools_allowed else None,
                grounding=grounding,
            )
            usage = _add_usage(usage, _usage_from(result))
            searched = _merge_grounding(searched, _grounding_from(result))
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
        grounded = _merge_grounding(searched, completion.grounding or GroundingInfo())
        return LlmCompletion(
            data=completion.data,
            usage=usage,
            tool_calls=tuple(calls),
            grounding=None if grounded.is_empty() else grounded,
        )

    def _client(self) -> Any:
        """The shared Agent Platform client (built once per project/location).

        A lazy import keeps `google.genai` out of the module import path. No API
        key: ADC supplies credentials. The image provider uses the same client.
        """
        return get_gemini_client(self.settings)

    async def _generate(
        self,
        *,
        model: str,
        contents: Any,
        system: str,
        schema: dict[str, Any],
        function_declarations: list[Any] | None,
        grounding: bool = False,
        temperature: float | None = None,
        max_attempts: int | None = None,
        max_output_tokens: int | None = None,
        thinking_level: str | None = None,
    ) -> Any:
        """One `generate_content` call, retrying transient failures."""
        from google.genai import errors as genai_errors
        from google.genai import types

        client = self._client()
        logger.info(
            "LLM call model=%s tools=%s grounding=%s",
            model,
            len(function_declarations) if function_declarations else 0,
            grounding,
        )
        config: dict[str, Any] = {
            "system_instruction": system,
            "response_mime_type": "application/json",
            "response_schema": schema,
        }
        if temperature is not None:
            config["temperature"] = temperature
        if max_output_tokens is not None:
            config["max_output_tokens"] = max_output_tokens
        if thinking_level is not None:
            config["thinking_config"] = {"thinking_level": thinking_level}
        if max_attempts is not None or self.settings.llm_max_attempts == 1:
            # The SDK defaults to five HTTP attempts inside each provider attempt.
            # Explicit call budgets must count upstream requests, including failures.
            config["http_options"] = {"retry_options": {"attempts": 1}}
        tool_entries: list[Any] = []
        if function_declarations:
            # Declarations only: we execute the calls ourselves (plain `generate_content`
            # cannot run SDK automatic function calling), so it is disabled explicitly.
            tool_entries.append(_tool(function_declarations))
            config["automatic_function_calling"] = {"disable": True}
        if grounding:
            # Google Search grounding. Gemini 3 supports it alongside the declarations.
            tool_entries.append(types.Tool(google_search=types.GoogleSearch()))
        if tool_entries:
            config["tools"] = tool_entries

        attempts = max(
            1, max_attempts if max_attempts is not None else self.settings.llm_max_attempts
        )
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
    return LlmCompletion(
        data=json.loads(text),
        usage=_usage_from(result),
        grounding=_grounding_from(result),
    )


def _grounding_from(result: Any) -> GroundingInfo:
    """Read grounding metadata (queries, web sources, Search Suggestions) off a result."""
    candidates = getattr(result, "candidates", None) or []
    metadata = getattr(candidates[0], "grounding_metadata", None) if candidates else None
    if metadata is None:
        return GroundingInfo()
    queries = tuple(getattr(metadata, "web_search_queries", None) or [])
    sources: list[GroundingSource] = []
    for chunk in getattr(metadata, "grounding_chunks", None) or []:
        web = getattr(chunk, "web", None)
        if web is None:
            continue
        sources.append(
            GroundingSource(
                title=getattr(web, "title", "") or "",
                uri=getattr(web, "uri", "") or "",
                domain=getattr(web, "domain", "") or "",
            )
        )
    suggestions = ""
    entry_point = getattr(metadata, "search_entry_point", None)
    if entry_point is not None:
        suggestions = getattr(entry_point, "rendered_content", "") or ""
    return GroundingInfo(
        queries=queries,
        sources=tuple(sources),
        search_suggestions_html=suggestions,
    )


def _merge_grounding(left: GroundingInfo, right: GroundingInfo) -> GroundingInfo:
    """Union two grounding results (a tool loop makes several search calls)."""
    queries = list(left.queries)
    for query in right.queries:
        if query not in queries:
            queries.append(query)
    sources = list(left.sources)
    seen = {source.uri for source in sources}
    for source in right.sources:
        if source.uri and source.uri in seen:
            continue
        sources.append(source)
        seen.add(source.uri)
    return GroundingInfo(
        queries=tuple(queries),
        sources=tuple(sources),
        search_suggestions_html=(left.search_suggestions_html or right.search_suggestions_html),
    )


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
