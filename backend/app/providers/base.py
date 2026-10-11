"""Provider interfaces.

Nothing in the app imports a Google SDK directly. Everything goes through one of these
interfaces, so all Google API usage lives in `app/providers/` and feature code stays
free of SDK imports and credentials handling.
"""

from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable


@dataclass(frozen=True)
class LlmUsage:
    """Token counts reported by the model after a call."""

    input_tokens: int = 0
    output_tokens: int = 0


@dataclass(frozen=True)
class MediaPart:
    """One media attachment for a multimodal LLM call (image or short video).

    `label` is a short human-readable tag (for example "frame @ 01:23") that the
    provider prepends as text so the model can tell several attachments apart.
    """

    mime_type: str
    data: bytes
    label: str = ""


@dataclass(frozen=True)
class ToolSpec:
    """A function the model may call, described in JSON-schema terms.

    Feature code declares tools with this provider-neutral shape; the provider turns
    them into SDK function declarations.
    """

    name: str
    description: str
    parameters: dict[str, Any]


@dataclass(frozen=True)
class ToolCall:
    """One function call the model made, plus the media the tool returned."""

    name: str
    arguments: dict[str, Any] = field(default_factory=dict)
    media: tuple[MediaPart, ...] = ()
    ok: bool = True
    error: str = ""


#: Executes a tool call and returns the media to show the model. Raising is treated as a
#: failed tool call; the run continues without the attachment.
ToolExecutor = Callable[[str, dict[str, Any]], Awaitable[Sequence[MediaPart]]]


@dataclass(frozen=True)
class GroundingSource:
    """One web source returned by Search grounding."""

    title: str = ""
    uri: str = ""
    domain: str = ""


@dataclass(frozen=True)
class GroundingInfo:
    """What Search grounding produced for a call, for citations and the UI."""

    queries: tuple[str, ...] = ()
    sources: tuple[GroundingSource, ...] = ()
    #: Google-provided "Search Suggestions" HTML. Must be displayed when present.
    search_suggestions_html: str = ""

    def is_empty(self) -> bool:
        return not (self.queries or self.sources or self.search_suggestions_html)


@dataclass(frozen=True)
class LlmCompletion:
    """A structured LLM answer plus what it cost in tokens and what tools it called."""

    data: dict[str, Any]
    usage: LlmUsage = field(default_factory=LlmUsage)
    tool_calls: tuple[ToolCall, ...] = ()
    grounding: GroundingInfo | None = None


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
        # Optional inline media (frames / short clips). Empty means text-only.
        media: Sequence[MediaPart] = (),
        # When set, give the model Google Search grounding.
        grounding: bool = False,
    ) -> LlmCompletion: ...

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
        # When set, Google Search is offered alongside the custom tools (Gemini 3).
        grounding: bool = False,
    ) -> LlmCompletion:
        """Run a function-calling loop, then return the final structured answer.

        The model may call the supplied tools zero or more times; each call is handed to
        `execute`, and whatever media it returns is attached to the function response so
        the model can see it. The loop stops when the model answers with the schema or
        the round/call budget is spent, and the final answer is parsed as JSON.
        """
        ...


@runtime_checkable
class SttProvider(Protocol):
    async def transcribe(
        self,
        *,
        gcs_uri: str,
        language_codes: list[str],
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


@dataclass(frozen=True)
class GeneratedImage:
    """One image returned by an image-generation model."""

    data: bytes
    mime_type: str


@runtime_checkable
class ImageGenProvider(Protocol):
    async def generate(
        self,
        *,
        model: str,
        prompt: str,
        count: int = 1,
        aspect_ratio: str = "16:9",
        image_size: str = "1K",
        # Reference images (for example a frame of the actual creator) that the model
        # should keep consistent. Empty means a from-scratch generation.
        reference_images: Sequence[MediaPart] = (),
        # When set, the model edits this image instead of generating from scratch.
        # `prompt` becomes the edit instruction.
        base_image: MediaPart | None = None,
    ) -> list[GeneratedImage]:
        """Generate or edit images from a prompt.

        Returns up to `count` images; a model may return fewer. Raising signals a hard
        failure the caller should surface to the user.
        """
        ...


@runtime_checkable
class VideoGenProvider(Protocol):
    async def start(
        self,
        *,
        model: str,
        prompt: str,
        duration_seconds: int,
        aspect_ratio: str,
    ) -> str: ...

    async def wait(self, operation_name: str) -> bytes: ...


@runtime_checkable
class SocialProvider(Protocol):
    async def fetch_posts(self, connection: dict[str, Any]) -> list[dict[str, Any]]: ...

    async def fetch_metrics(
        self, connection: dict[str, Any], date_range: dict[str, str]
    ) -> list[dict[str, Any]]: ...

    async def fetch_comments(self, connection: dict[str, Any]) -> list[dict[str, Any]]: ...


class EmbeddingProvider(Protocol):
    def embed(self, text: str, *, media: MediaPart | None = None) -> list[float]: ...
