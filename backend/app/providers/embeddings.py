"""Gemini Embedding 2 through the existing ADC-backed Vertex client."""

import math

from app.config import Settings
from app.providers.base import MediaPart
from app.providers.gemini_client import get_gemini_client


class GeminiEmbeddingProvider:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def embed(self, text: str, *, media: MediaPart | None = None) -> list[float]:
        from google.genai import types

        parts = [types.Part.from_text(text=text)]
        if media is not None:
            parts.append(types.Part.from_bytes(data=media.data, mime_type=media.mime_type))
        result = get_gemini_client(self.settings).models.embed_content(
            model=self.settings.model_embedding,
            contents=types.Content(parts=parts),
            config=types.EmbedContentConfig(
                output_dimensionality=self.settings.embedding_dimensions,
                # One reserved daily slot covers exactly one provider request.
                http_options=types.HttpOptions(
                    retry_options=types.HttpRetryOptions(attempts=1)
                ),
            ),
        )
        embeddings = result.embeddings or []
        if len(embeddings) != 1:
            raise ValueError("Expected one embedding for one creator passage")
        vector = [float(value) for value in (embeddings[0].values or [])]
        if len(vector) != self.settings.embedding_dimensions or not all(
            math.isfinite(value) for value in vector
        ):
            raise ValueError("Embedding has invalid dimensions or values")
        norm = math.sqrt(sum(value * value for value in vector))
        if norm <= 0:
            raise ValueError("Embedding has zero norm")
        return [value / norm for value in vector]
