"""Shared Agent Platform (Vertex AI) GenAI client.

Both the text LLM and image-generation providers talk to Agent Platform with the same
`genai.Client(vertexai=True, project=..., location=...)`. Building a client is not free, so
one client is cached per project/location and shared. The SDK import stays lazy so importing
`app.providers` never pulls in `google.genai`.
"""

from functools import cache
from typing import Any

from app.config import Settings


@cache
def _client(project: str, location: str) -> Any:
    from google import genai

    return genai.Client(vertexai=True, project=project, location=location)


def get_gemini_client(settings: Settings) -> Any:
    return _client(settings.project_id, settings.vertex_location)


def get_llm_client(settings: Settings) -> Any:
    """Client for text generation, on its own endpoint (see `Settings.llm_location`)."""
    return _client(settings.project_id, settings.llm_location)


__all__ = ["get_gemini_client", "get_llm_client"]
