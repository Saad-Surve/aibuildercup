"""One bounded Veo request, with resumable polling and inline video output.

No submission retries: a transport failure may conceal a billed operation. The worker
persists the returned name before polling. Polling may retry capacity errors without
ever submitting another generation. Inline output prevents a deleted project from
receiving a late GCS object from the model service.
"""

import asyncio
import time

from app.config import Settings
from app.providers.gemini_client import get_gemini_client


class VideoGenError(RuntimeError):
    def __init__(self, message: str, *, terminal: bool = False) -> None:
        super().__init__(message)
        self.terminal = terminal


class VideoGenProvider:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def _client(self):
        # Veo is regional even when the text/image providers use the global endpoint.
        return get_gemini_client(
            self.settings.model_copy(update={"vertex_location": "us-central1"})
        )

    async def start(
        self,
        *,
        model: str,
        prompt: str,
        duration_seconds: int,
        aspect_ratio: str,
    ) -> str:
        from google.genai import types

        if duration_seconds != 6 or aspect_ratio not in ("16:9", "9:16"):
            raise VideoGenError("Visual inserts must be six seconds in a supported aspect ratio.")
        operation = await self._client().aio.models.generate_videos(
            model="veo-3.1-fast-generate-001" if model == "veo-3.1-fast" else model,
            prompt=prompt,
            config=types.GenerateVideosConfig(
                number_of_videos=1,
                duration_seconds=6,
                aspect_ratio=aspect_ratio,
                resolution="720p",
                generate_audio=False,
                person_generation="allow_adult",
            ),
        )
        if not operation.name:
            raise VideoGenError("The video service did not return an operation name.")
        return str(operation.name)

    async def wait(self, operation_name: str) -> bytes:
        from google.genai import types

        operation = types.GenerateVideosOperation.model_validate({"name": operation_name})
        deadline = time.monotonic() + self.settings.videogen_poll_timeout_seconds
        while time.monotonic() < deadline:
            await asyncio.sleep(10)
            try:
                operation = await self._client().aio.operations.get(operation)
            except Exception as exc:
                code = getattr(exc, "code", None)
                if code in (429, 500, 502, 503, 504):
                    continue
                raise VideoGenError(
                    "Could not poll the video operation; retry to resume it."
                ) from exc
            if not operation.done:
                continue
            if operation.error:
                raise VideoGenError(
                    "Video generation failed. The paid allowance remains reserved.", terminal=True
                )
            result = operation.response or operation.result
            videos = result.generated_videos if result else None
            if not videos or not videos[0].video or not videos[0].video.video_bytes:
                raise VideoGenError(
                    "No video was returned; the prompt may have been filtered.", terminal=True
                )
            return bytes(videos[0].video.video_bytes)
        raise VideoGenError(
            "Video generation is still pending. Retry to resume the same operation."
        )
