"""Speech-to-Text provider.

Thin wrapper over Speech-to-Text V2 batch recognition (`chirp_3` in `us-central1`; Chirp is
not GA in `us-east1`). Feature code calls this provider, never `google.cloud.speech` directly.
"""

import logging
from typing import Any

from app.config import Settings

logger = logging.getLogger(__name__)


class SttProvider:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def transcribe(
        self,
        *,
        gcs_uri: str,
        language: str,
        model: str,
    ) -> dict[str, Any]:
        return await self._real(gcs_uri=gcs_uri, language=language, model=model)

    async def _real(self, *, gcs_uri: str, language: str, model: str) -> dict[str, Any]:
        import asyncio

        from google.cloud import speech_v2

        client = speech_v2.SpeechClient(
            client_options={"api_endpoint": f"{self.settings.region}-speech.googleapis.com"}
        )
        recognizer = (
            f"projects/{self.settings.project_id}/locations/{self.settings.region}"
            "/recognizers/_"
        )
        config = speech_v2.RecognitionConfig(
            auto_decoding_config=speech_v2.AutoDetectDecodingConfig(),
            language_codes=[language],
            model=model,
            features=speech_v2.RecognitionFeatures(
                enable_word_time_offsets=True,
                enable_automatic_punctuation=True,
            ),
        )
        request = speech_v2.BatchRecognizeRequest(
            recognizer=recognizer,
            config=config,
            files=[speech_v2.BatchRecognizeFileMetadata(uri=gcs_uri)],
        )
        logger.info("STT batch recognition via %s (%s)", gcs_uri, model)
        operation = client.batch_recognize(request=request)
        # Batch recognition is long-running; poll in a thread so the event loop stays free.
        # Ack deadline max is 600s, so cap the wait there.
        result = await asyncio.to_thread(operation.result, 600)
        return _operation_to_dict(result)

    def gcs_uri_for(self, storage_path: str) -> str:
        return f"gs://{self.settings.media_bucket}/{storage_path}"


def _operation_to_dict(result: Any) -> dict[str, Any]:
    """Normalise a BatchRecognizeResponse into plain JSON."""
    words: list[dict[str, Any]] = []
    for file_result in getattr(result, "results", {}).values():
        for alt in getattr(file_result, "alternatives", []):
            for word_info in getattr(alt, "words", []) or []:
                words.append(
                    {
                        "word": getattr(word_info, "word", ""),
                        "startMs": _duration_to_ms(
                            getattr(word_info, "start_offset", None)
                        ),
                        "endMs": _duration_to_ms(getattr(word_info, "end_offset", None)),
                    }
                )
    return {"words": words}


def _duration_to_ms(duration: Any) -> int:
    if duration is None:
        return 0
    seconds = getattr(duration, "seconds", 0) or 0
    nanos = getattr(duration, "nanos", 0) or 0
    return int(seconds * 1000 + nanos / 1_000_000)
