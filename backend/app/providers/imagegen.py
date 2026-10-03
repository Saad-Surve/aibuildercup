"""Image generation provider.

Wraps Gemini image models on Agent Platform (Vertex AI) — "Nano Banana" — authenticated with
Application Default Credentials through the shared `get_gemini_client`. Feature code calls this
provider, never `google.genai` directly.

Why this model family (chosen in `docs/current-progress/2026-10-03-1015`):

- It accepts **reference images**, so a thumbnail can be built around the creator's actual face
  instead of an invented one.
- It **edits conversationally**: feeding a generated image back with an instruction produces a
  new revision, which is how the thumbnail studio's "make the text bigger" loop works.
- It renders **legible text** inside the image, unlike plain diffusion models.
"""

import asyncio
import logging
import time
from collections.abc import Sequence
from typing import Any

from app.config import Settings
from app.providers.base import GeneratedImage, MediaPart
from app.providers.gemini_client import get_gemini_client

logger = logging.getLogger(__name__)

# Statuses worth retrying: the model was overloaded, rate-limited, or a transient server error.
TRANSIENT_STATUS_CODES = frozenset({429, 500, 502, 503, 504})

#: Aspect ratios Gemini image models accept. Kept as a guard so a typo fails fast.
SUPPORTED_ASPECT_RATIOS = frozenset(
    {"1:1", "2:3", "3:2", "3:4", "4:3", "4:5", "5:4", "9:16", "16:9", "21:9"}
)
#: Image sizes Gemini image models accept.
SUPPORTED_IMAGE_SIZES = frozenset({"512", "1K", "2K", "4K"})


class ImageGenError(RuntimeError):
    """Raised when the model returns no image or the call fails permanently."""


class ImageGenProvider:
    """`ImageGenProvider` backed by Gemini image models on Agent Platform."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def generate(
        self,
        *,
        model: str,
        prompt: str,
        count: int = 1,
        aspect_ratio: str = "16:9",
        image_size: str = "1K",
        reference_images: Sequence[MediaPart] = (),
        base_image: MediaPart | None = None,
    ) -> list[GeneratedImage]:
        from google.genai import types

        if aspect_ratio not in SUPPORTED_ASPECT_RATIOS:
            raise ImageGenError(f"Unsupported aspect ratio: {aspect_ratio!r}")
        if image_size not in SUPPORTED_IMAGE_SIZES:
            raise ImageGenError(f"Unsupported image size: {image_size!r}")

        parts: list[Any] = [types.Part.from_text(text=prompt)]
        for reference in reference_images:
            if reference.label:
                parts.append(types.Part.from_text(text=reference.label))
            parts.append(
                types.Part.from_bytes(
                    data=reference.data, mime_type=reference.mime_type
                )
            )
        if base_image is not None:
            # The image being edited. Ordering after the instruction text lets the
            # model read the instruction first, then the pixels.
            parts.append(
                types.Part.from_bytes(
                    data=base_image.data, mime_type=base_image.mime_type
                )
            )

        config: dict[str, Any] = {
            "response_modalities": ["IMAGE"],
            "image_config": {"aspect_ratio": aspect_ratio, "image_size": image_size},
        }

        logger.info(
            "image gen model=%s aspect=%s size=%s refs=%d edit=%s",
            model,
            aspect_ratio,
            image_size,
            len(reference_images),
            base_image is not None,
        )
        result = await asyncio.to_thread(
            self._generate_with_retry,
            model=model,
            parts=parts,
            config=config,
        )
        images = _images_from(result)
        if not images:
            raise ImageGenError("The image model returned no image.")
        return images[: max(1, count)]

    def _generate_with_retry(
        self, *, model: str, parts: list[Any], config: dict[str, Any]
    ) -> Any:
        from google.genai import errors as genai_errors

        client = get_gemini_client(self.settings)
        attempts = max(1, self.settings.llm_max_attempts)
        for attempt in range(1, attempts + 1):
            try:
                return client.models.generate_content(
                    model=model, contents=parts, config=config
                )
            except genai_errors.APIError as exc:
                code = getattr(exc, "code", None)
                if code not in TRANSIENT_STATUS_CODES or attempt == attempts:
                    raise
                logger.warning(
                    "image gen returned %s; retry %d/%d", code, attempt, attempts
                )
                time.sleep(self.settings.llm_retry_base_seconds * (2 ** (attempt - 1)))
        raise ImageGenError("The image model returned no result.")


def _images_from(result: Any) -> list[GeneratedImage]:
    images: list[GeneratedImage] = []
    for part in list(getattr(result, "parts", None) or []):
        inline = getattr(part, "inline_data", None)
        data = getattr(inline, "data", None) if inline is not None else None
        if not data:
            continue
        mime_type = getattr(inline, "mime_type", None) or "image/png"
        images.append(GeneratedImage(data=data, mime_type=mime_type))
    return images


__all__ = [
    "ImageGenError",
    "ImageGenProvider",
    "SUPPORTED_ASPECT_RATIOS",
    "SUPPORTED_IMAGE_SIZES",
]
