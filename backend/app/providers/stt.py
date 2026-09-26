"""Speech-to-Text provider.

Thin wrapper over the Speech-to-Text V2 API using batch recognition for GCS-hosted
video/audio (in `us-central1`). Feature code calls this provider, never
`google.cloud.speech` directly.
"""

import logging
import os
from typing import Any
from urllib.parse import urlparse

from app.config import Settings

logger = logging.getLogger(__name__)

# STT V2 auto-detection rejects the AAC-in-video family ("Audio data does not appear to be in
# a supported encoding"), so those containers get an explicit decoding config. Audio-only
# formats (mp3/webm/ogg/flac/wav) are still auto-detected.
_AAC_ENCODINGS_BY_EXTENSION = {
    ".mp4": "MP4_AAC",
    ".m4v": "MP4_AAC",
    ".mov": "MOV_AAC",
    ".m4a": "M4A_AAC",
}


class SttProvider:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def transcribe(
        self,
        *,
        gcs_uri: str,
        language_codes: list[str],
        model: str,
        enable_diarization: bool = False,
    ) -> dict[str, Any]:
        return await self._real(
            gcs_uri=gcs_uri,
            language_codes=language_codes,
            model=model,
            enable_diarization=enable_diarization,
        )

    async def _real(
        self,
        *,
        gcs_uri: str,
        language_codes: list[str],
        model: str,
        enable_diarization: bool = False,
    ) -> dict[str, Any]:
        import asyncio

        from google.cloud import speech_v2

        client = speech_v2.SpeechClient(
            client_options={
                "api_endpoint": f"{self.settings.stt_region}-speech.googleapis.com"
            }
        )
        recognizer = (
            f"projects/{self.settings.project_id}/locations/{self.settings.stt_region}"
            "/recognizers/_"
        )
        features = speech_v2.RecognitionFeatures(
            enable_word_time_offsets=True,
            enable_automatic_punctuation=True,
        )
        if enable_diarization:
            # Chirp 3 assigns a `speaker_label` per word when diarization is requested. The
            # service decides the speaker count (min/max are documented as not yet used), and
            # word time offsets — which diarization depends on — are already enabled above.
            features.diarization_config = speech_v2.SpeakerDiarizationConfig()
        config = speech_v2.RecognitionConfig(
            **self._decoding_config(speech_v2, gcs_uri),
            language_codes=language_codes,
            model=model,
            features=features,
        )
        # Batch recognition writes nothing inline unless asked: request inline results
        # so word timings come back in the operation response (fine for demo-scale
        # videos; hour-long files would use a GCS output prefix instead).
        output_config = speech_v2.RecognitionOutputConfig(
            inline_response_config=speech_v2.InlineOutputConfig()
        )
        request = speech_v2.BatchRecognizeRequest(
            recognizer=recognizer,
            config=config,
            files=[speech_v2.BatchRecognizeFileMetadata(uri=gcs_uri)],
            recognition_output_config=output_config,
        )
        logger.info(
            "STT v2 batch recognition via %s (model=%s, languages=%s, diarization=%s)",
            gcs_uri,
            model,
            ",".join(language_codes),
            enable_diarization,
        )
        try:
            operation = await asyncio.to_thread(client.batch_recognize, request=request)
            # Batch recognition is long-running; poll in a thread so the event loop stays free.
            # Ack deadline max is 600s, so cap the wait there.
            result = await asyncio.to_thread(operation.result, 600)
            return _response_to_dict(result)
        except Exception as exc:
            # Diarization is optional: if a model/region rejects it, fall back to plain
            # transcription instead of failing the whole job over a nice-to-have.
            if not enable_diarization or "diarization" not in str(exc).lower():
                raise
            logger.warning("STT rejected diarization (%s); retrying without it", exc)
            return await self._real(
                gcs_uri=gcs_uri,
                language_codes=language_codes,
                model=model,
                enable_diarization=False,
            )

    def _decoding_config(self, speech_v2: Any, gcs_uri: str) -> dict[str, Any]:
        """Pick a decoding config for the container, falling back to auto-detection."""
        extension = os.path.splitext(urlparse(gcs_uri).path)[1].lower()
        encoding_name = _AAC_ENCODINGS_BY_EXTENSION.get(extension)
        if encoding_name is None:
            return {"auto_decoding_config": speech_v2.AutoDetectDecodingConfig()}
        encoding = getattr(speech_v2.ExplicitDecodingConfig.AudioEncoding, encoding_name)
        return {
            "explicit_decoding_config": speech_v2.ExplicitDecodingConfig(
                encoding=encoding,
                sample_rate_hertz=self.settings.stt_sample_rate_hz,
                audio_channel_count=self.settings.stt_audio_channel_count,
            )
        }

    def gcs_uri_for(self, storage_path: str) -> str:
        return f"gs://{self.settings.media_bucket}/{storage_path}"


def _response_to_dict(result: Any) -> dict[str, Any]:
    """Normalise a BatchRecognizeResponse (inline results) into plain JSON.

    Shape: `results[uri].inline_result.transcript.results[].alternatives[].words[]`, each word
    carrying `word`, `start_offset`, `end_offset` and (when diarization is on) `speaker_label`.
    Also returns the language the service detected, so the worker can persist it for
    multilingual uploads.
    """
    words: list[dict[str, Any]] = []
    language: str | None = None
    for file_result in getattr(result, "results", {}).values():
        _raise_for_file_error(file_result)
        bundle = _transcript_bundle(file_result)
        if bundle is None:
            continue
        for recognition_result in getattr(bundle, "results", []) or []:
            if language is None:
                language = getattr(recognition_result, "language_code", "") or None
            for alt in getattr(recognition_result, "alternatives", []) or []:
                for word_info in getattr(alt, "words", []) or []:
                    speaker = int(getattr(word_info, "speaker_label", 0) or 0)
                    words.append(
                        {
                            "word": getattr(word_info, "word", ""),
                            "startMs": _duration_to_ms(
                                getattr(word_info, "start_offset", None)
                            ),
                            "endMs": _duration_to_ms(getattr(word_info, "end_offset", None)),
                            # Proto3 omits a zero speaker label; treat it as "undiarized".
                            "speaker": speaker or None,
                        }
                    )
    return {"words": words, "language": language}


def _raise_for_file_error(file_result: Any) -> None:
    """Batch recognition reports per-file failures in-band; surface them as real errors."""
    error = getattr(file_result, "error", None)
    code = getattr(error, "code", 0) if error is not None else 0
    if code:
        message = getattr(error, "message", "") or "unknown error"
        raise RuntimeError(f"Speech-to-Text failed: {message}")


def _transcript_bundle(file_result: Any) -> Any:
    """Return the results container from an inline result (or the file-level transcript)."""
    inline = getattr(file_result, "inline_result", None)
    if inline is not None:
        transcript = getattr(inline, "transcript", None)
        if transcript is not None and len(getattr(transcript, "results", [])) > 0:
            return transcript
    return getattr(file_result, "transcript", None)


def _duration_to_ms(duration: Any) -> int:
    if duration is None:
        return 0
    seconds = getattr(duration, "seconds", 0) or 0
    nanos = getattr(duration, "nanos", 0) or 0
    return int(seconds * 1000 + nanos / 1_000_000)
