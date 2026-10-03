"""Text-to-Speech provider.

Thin wrapper over Cloud Text-to-Speech. Feature code calls this provider, never
`google.cloud.texttospeech` directly. Each call returns encoded MP3 audio for one line of
speech; the dubbing worker decodes the MP3 with FFmpeg at the configured sample rate so the
whole track can be assembled on a single timeline.

Authentication is Application Default Credentials, same as every other provider.
"""

import logging
from typing import Any

from app.config import Settings

logger = logging.getLogger(__name__)


class TtsProvider:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        # Building a client is not free and the worker synthesizes one clip per
        # segment, so the client is built once and reused.
        self._cached_client: object | None = None

    async def synthesize(self, *, text: str, language: str, voice: str) -> bytes:
        if not text.strip():
            return b""
        return await self._real(text=text, language=language, voice=voice)

    async def _real(self, *, text: str, language: str, voice: str) -> bytes:
        import asyncio

        from google.cloud import texttospeech

        client = self._client(texttospeech)
        request = texttospeech.SynthesizeSpeechRequest(
            input=texttospeech.SynthesisInput(text=text),
            voice=texttospeech.VoiceSelectionParams(language_code=language, name=voice),
            audio_config=texttospeech.AudioConfig(
                audio_encoding=texttospeech.AudioEncoding.MP3,
                sample_rate_hertz=self.settings.tts_sample_rate_hz,
            ),
        )
        logger.info("TTS call voice=%s language=%s chars=%d", voice, language, len(text))
        response = await asyncio.to_thread(client.synthesize_speech, request=request)
        audio = bytes(response.audio_content or b"")
        if not audio:
            raise RuntimeError("Text-to-Speech returned no audio")
        return audio

    def _client(self, texttospeech: Any) -> Any:
        if self._cached_client is None:
            self._cached_client = texttospeech.TextToSpeechClient()
        return self._cached_client
