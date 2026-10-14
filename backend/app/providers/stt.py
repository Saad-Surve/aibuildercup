"""Speech-to-Text provider.

Thin wrapper over the Speech-to-Text V2 API using batch recognition for GCS-hosted
video/audio (in the `us` multi-region). Feature code calls this provider, never
`google.cloud.speech` directly.
"""

import asyncio
import logging
import os
import random
import time
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


class SttSubmissionError(RuntimeError):
    """Submission failed; only an explicit rejection is safe to submit again."""

    def __init__(self, message: str, *, rejected: bool = False) -> None:
        super().__init__(message)
        self.rejected = rejected


class SttPollingError(RuntimeError):
    """Polling failed or timed out; retain the name and resume the same operation."""


class SttRecognitionError(RuntimeError):
    """A rejected request or completed operation reported a recognition failure."""

    def __init__(self, message: str, *, code: int) -> None:
        super().__init__(message)
        self.code = code

    @property
    def diarization_rejected(self) -> bool:
        return self.code in (3, 12) and "diarization" in str(self).lower()

    @property
    def can_normalize(self) -> bool:
        # INTERNAL is the known broken MP4 mux failure. INVALID_ARGUMENT is only
        # eligible when it actually concerns the audio/container, not language settings.
        return self.code == 13 or (
            self.code == 3
            and not self.diarization_rejected
            and any(word in str(self).lower() for word in ("audio", "encoding", "container"))
        )


class SttProvider:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def _client(self) -> Any:
        from google.cloud import speech_v2

        return speech_v2.SpeechClient(
            client_options={"api_endpoint": f"{self.settings.stt_region}-speech.googleapis.com"}
        )

    async def start(
        self,
        *,
        gcs_uri: str,
        language_codes: list[str],
        model: str,
        enable_diarization: bool = False,
        timeout_seconds: float | None = None,
    ) -> str:
        """Submit recognition; retry only an explicit submission-time 429.

        Disable SDK retries so an ambiguous transport failure cannot create another
        billed batch operation. The worker persists the name before calling wait().
        """
        deadline = self._deadline(timeout_seconds)
        from google.cloud import speech_v2

        client = self._client()
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
        from google.api_core.exceptions import (
            InvalidArgument,
            MethodNotImplemented,
            ResourceExhausted,
            ServiceUnavailable,
        )

        attempts = max(1, self.settings.stt_max_attempts)
        for attempt in range(1, attempts + 1):
            if time.monotonic() >= deadline:
                raise SttSubmissionError("STT submission deadline expired.", rejected=True)
            try:
                operation = await asyncio.to_thread(
                    client.batch_recognize,
                    request=request,
                    retry=None,
                    timeout=self._rpc_timeout(deadline),
                )
            except (ResourceExhausted, ServiceUnavailable) as exc:
                # 429 and 503 mean the request was not accepted, so retrying is safe.
                if attempt == attempts or time.monotonic() >= deadline:
                    raise SttSubmissionError(str(exc), rejected=True) from exc
                await self._backoff(attempt, deadline, "submission")
                if time.monotonic() >= deadline:
                    raise SttSubmissionError(str(exc), rejected=True) from exc
                continue
            except InvalidArgument as exc:
                raise SttRecognitionError(str(exc), code=3) from exc
            except MethodNotImplemented as exc:
                raise SttRecognitionError(str(exc), code=12) from exc
            except Exception as exc:
                raise SttSubmissionError(
                    "STT submission outcome is unknown; automatic resubmission is blocked."
                ) from exc
            name = operation.operation.name
            if not name:
                raise SttSubmissionError("STT did not return an operation name.")
            return str(name)
        raise SttSubmissionError("STT submission deadline expired.", rejected=True)

    async def wait(
        self, operation_name: str, *, timeout_seconds: float | None = None
    ) -> dict[str, Any]:
        """Poll GetOperation by name with bounded retries and one total deadline.

        No path in this method submits recognition. Capacity and transport errors are
        polling failures even when their message mentions audio or diarization.
        """
        deadline = self._deadline(timeout_seconds)
        from google.api_core.exceptions import (
            DeadlineExceeded,
            ResourceExhausted,
            ServiceUnavailable,
        )
        from google.cloud import speech_v2

        client = self._client()
        failures = 0
        while time.monotonic() < deadline:
            try:
                operation = await asyncio.to_thread(
                    client.transport.operations_client.get_operation,
                    operation_name,
                    retry=None,
                    timeout=self._rpc_timeout(deadline),
                )
            except (ResourceExhausted, ServiceUnavailable, DeadlineExceeded) as exc:
                failures += 1
                if failures >= max(1, self.settings.stt_max_attempts):
                    raise SttPollingError(
                        f"Could not poll STT operation {operation_name}; retry to resume it."
                    ) from exc
                await self._backoff(failures, deadline, "polling")
                continue
            except Exception as exc:
                raise SttPollingError(
                    f"Could not poll STT operation {operation_name}; retry to resume it."
                ) from exc
            failures = 0
            if operation.done:
                if operation.HasField("error"):
                    raise SttRecognitionError(operation.error.message, code=operation.error.code)
                result = speech_v2.BatchRecognizeResponse()
                if not operation.response.Unpack(speech_v2.BatchRecognizeResponse.pb(result)):
                    raise SttPollingError("STT returned an unexpected operation response.")
                return _response_to_dict(result)
            await asyncio.sleep(
                min(self.settings.stt_poll_interval_seconds, max(0, deadline - time.monotonic()))
            )
        raise SttPollingError(
            f"STT operation {operation_name} is still pending; retry to resume it."
        )

    def _deadline(self, timeout_seconds: float | None) -> float:
        timeout = self.settings.stt_job_timeout_seconds
        if timeout_seconds is not None:
            timeout = min(timeout, timeout_seconds)
        return time.monotonic() + max(0, timeout)

    def _rpc_timeout(self, deadline: float) -> float:
        return min(self.settings.stt_rpc_timeout_seconds, max(0.001, deadline - time.monotonic()))

    async def _backoff(self, attempt: int, deadline: float, phase: str) -> None:
        cap = min(
            self.settings.stt_retry_max_seconds,
            self.settings.stt_retry_base_seconds * (2 ** min(attempt - 1, 30)),
        )
        delay = min(random.uniform(cap / 2, cap), max(0, deadline - time.monotonic()))
        logger.warning("STT %s throttled/unavailable: retry %d in %.1fs", phase, attempt, delay)
        await asyncio.sleep(delay)

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
                            "startMs": _duration_to_ms(getattr(word_info, "start_offset", None)),
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
        raise SttRecognitionError(f"Speech-to-Text failed: {message}", code=int(code))


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
