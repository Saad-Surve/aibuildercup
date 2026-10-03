"""Video context tools for the reviewer agents.

Two operations, both backed by FFmpeg:

- `extract_frame`: one still image at a timestamp.
- `cut_clip`: a short clip centred on a timestamp (default +/- 5s).

Reviewers request them mid-review (see `app/agents/reviewer_base.py`): when the
transcript alone is ambiguous, a reviewer can ask to *see* the moment it is about
to flag, and the second pass grades with that footage in front of it.

The module is pure media handling: it knows nothing about GCS or Firestore. The
caller supplies a `source` FFmpeg can open (a local path, or an HTTPS signed URL so
the API never has to download a multi-hundred-megabyte video to disk). Output is
returned in memory as `MediaPart`s; nothing is persisted, so there is no delete
pathway to wire up.
"""

import asyncio
import logging
import shutil
import subprocess
import threading
from collections.abc import Callable
from typing import Any, Final, Protocol, runtime_checkable

from app.providers.base import MediaPart, ToolSpec

logger = logging.getLogger(__name__)

TOOL_EXTRACT_FRAME: Final = "extract_frame"
TOOL_CUT_CLIP: Final = "cut_clip"
TOOL_NAMES: Final = frozenset({TOOL_EXTRACT_FRAME, TOOL_CUT_CLIP})

#: FFmpeg is quick for a still; a short clip re-encode is bounded too.
_FRAME_TIMEOUT_SECONDS: Final = 30
_CLIP_TIMEOUT_SECONDS: Final = 90

#: JSON-schema parameters shared by both tools (a single ms offset).
_TIMESTAMP_PARAMETERS: Final[dict[str, Any]] = {
    "type": "object",
    "properties": {
        "timestampMs": {
            "type": "integer",
            "description": "Offset from the start of the video, in milliseconds.",
        },
        "reason": {
            "type": "string",
            "description": "One line on why this moment needs to be seen.",
        },
    },
    "required": ["timestampMs"],
}


def review_tool_specs(*, clip_window_seconds: int = 5) -> tuple[ToolSpec, ...]:
    """The tools a reviewer may call, described for the LLM."""
    return (
        ToolSpec(
            name=TOOL_EXTRACT_FRAME,
            description=(
                "Get one still frame from the video at a timestamp, as an image. Use it "
                "to check on-screen text, a chart, a face, a costume, or any single "
                "moment the transcript cannot settle."
            ),
            parameters=_TIMESTAMP_PARAMETERS,
        ),
        ToolSpec(
            name=TOOL_CUT_CLIP,
            description=(
                f"Get a short video clip of roughly {clip_window_seconds} seconds either "
                "side of a timestamp, with audio removed. Use it when motion, a reaction, "
                "an edit, or timing matters and a still would not be enough."
            ),
            parameters=_TIMESTAMP_PARAMETERS,
        ),
    )


class VideoToolError(RuntimeError):
    """Raised when FFmpeg cannot produce the requested output."""


@runtime_checkable
class ContextArtifactStore(Protocol):
    """Persists the media a reviewer fetched so the UI can show it later."""

    def save(
        self, part: MediaPart, *, reviewer_run_id: str, tool: str, index: int
    ) -> str:
        """Store `part` and return its object path."""
        ...


class GcsContextArtifactStore:
    """`ContextArtifactStore` backed by Cloud Storage, under the project prefix.

    Objects live at `{project}/review-context/{analysisRunId}/{reviewerRunId}/...`, so the
    existing recursive project delete covers them.
    """

    def __init__(self, storage: Any, prefix: str) -> None:
        self._storage = storage
        self._prefix = prefix

    def save(
        self, part: MediaPart, *, reviewer_run_id: str, tool: str, index: int
    ) -> str:
        extension = _extension_for(part.mime_type)
        safe_reviewer = reviewer_run_id or "reviewer"
        path = f"{self._prefix}{safe_reviewer}/{index:02d}-{tool}.{extension}"
        self._storage.upload_bytes(path, part.data, content_type=part.mime_type)
        return path


def _extension_for(mime_type: str) -> str:
    if mime_type == "image/jpeg":
        return "jpg"
    if mime_type == "image/png":
        return "png"
    if mime_type == "video/mp4":
        return "mp4"
    return "bin"


def _argument_ms(arguments: dict[str, Any]) -> int:
    """Read `timestampMs` from a tool call, rejecting anything non-integral."""
    value = arguments.get("timestampMs")
    if isinstance(value, bool) or value is None:
        raise ValueError("timestampMs is required")
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("timestampMs must be an integer") from exc


def ffmpeg_available(ffmpeg_path: str = "ffmpeg") -> bool:
    return shutil.which(ffmpeg_path) is not None


def format_timestamp(ms: int) -> str:
    ms = max(0, int(ms))
    minutes, remainder = divmod(ms, 60_000)
    seconds, millis = divmod(remainder, 1000)
    return f"{minutes:02d}:{seconds:02d}.{millis // 100:01d}"


def run_ffmpeg(args: list[str], *, timeout_seconds: int) -> bytes:
    """Run FFmpeg writing its single output stream to stdout as bytes."""
    try:
        completed = subprocess.run(
            args,
            capture_output=True,
            timeout=timeout_seconds,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise VideoToolError(f"ffmpeg timed out after {timeout_seconds}s") from exc
    if completed.returncode != 0:
        detail = completed.stderr.decode("utf-8", "replace").strip().splitlines()
        raise VideoToolError(detail[-1] if detail else "ffmpeg failed")
    if not completed.stdout:
        raise VideoToolError("ffmpeg produced no output")
    return completed.stdout


def probe_duration_ms(
    source: str, *, ffprobe_path: str = "ffprobe", timeout_seconds: int = 30
) -> int | None:
    """Real media duration via `ffprobe`, or None when unavailable/unreadable.

    `source` may be a local path or a signed URL. Returns None (never raises) so callers
    can fall back to estimating from the transcript.
    """
    if not source or shutil.which(ffprobe_path) is None:
        return None
    try:
        completed = subprocess.run(
            [
                ffprobe_path,
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "default=nw=1:nk=1",
                source,
            ],
            capture_output=True,
            timeout=timeout_seconds,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if completed.returncode != 0:
        return None
    lines = completed.stdout.decode("utf-8", "replace").strip().splitlines()
    if not lines:
        return None
    try:
        seconds = float(lines[-1])
    except ValueError:
        return None
    if seconds <= 0:
        return None
    return int(seconds * 1000)


def run_ffmpeg_command(args: list[str], *, timeout_seconds: int) -> None:
    """Run FFmpeg writing to a file/named output (no stdout capture of media)."""
    try:
        completed = subprocess.run(
            args, capture_output=True, timeout=timeout_seconds, check=False
        )
    except subprocess.TimeoutExpired as exc:
        raise VideoToolError(f"ffmpeg timed out after {timeout_seconds}s") from exc
    if completed.returncode != 0:
        detail = completed.stderr.decode("utf-8", "replace").strip().splitlines()
        tail = " | ".join(detail[-3:]) if detail else "ffmpeg failed"
        raise VideoToolError(tail)


def run_ffmpeg_with_progress(
    args: list[str],
    *,
    timeout_seconds: int,
    duration_seconds: float,
    on_progress: Callable[[float], None],
) -> None:
    """Run FFmpeg and report encode progress as a fraction in `[0, 1]`.

    FFmpeg is asked for machine-readable progress on stdout (`-progress pipe:1`,
    `-nostats`), one `key=value` line per update. `on_progress` is invoked with
    `out_time / duration_seconds`, clamped, and once more with `1.0` when the
    encode finishes. `on_progress` runs on the calling (worker) thread.

    stderr is drained on a daemon thread so a chatty encoder cannot fill the pipe
    and stall, and a watchdog kills the process if it exceeds `timeout_seconds`
    (`subprocess.run`'s timeout is not available on the streaming path).
    """
    process = subprocess.Popen(
        [args[0], "-progress", "pipe:1", "-nostats", *args[1:]],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
    )
    timed_out = threading.Event()

    def _kill_on_timeout() -> None:
        timed_out.set()
        process.kill()

    watchdog = threading.Timer(max(1, int(timeout_seconds)), _kill_on_timeout)
    watchdog.daemon = True
    watchdog.start()

    stderr_tail: list[str] = []

    def _drain_stderr() -> None:
        if process.stderr is None:
            return
        for line in process.stderr:
            text = line.rstrip()
            if text:
                stderr_tail.append(text)
                del stderr_tail[:-3]

    reader = threading.Thread(target=_drain_stderr, daemon=True)
    reader.start()

    try:
        if process.stdout is not None:
            for line in process.stdout:
                key, separator, value = line.strip().partition("=")
                if not separator:
                    continue
                if key in {"out_time_us", "out_time_ms"} and duration_seconds > 0:
                    # FFmpeg reports both keys in microseconds (`out_time_ms` is a
                    # historical misnomer); divide to get seconds of encoded output.
                    try:
                        encoded_seconds = int(value) / 1_000_000
                    except ValueError:
                        continue
                    on_progress(min(1.0, max(0.0, encoded_seconds / duration_seconds)))
                elif key == "progress" and value == "end":
                    on_progress(1.0)
        process.wait()
    finally:
        watchdog.cancel()
        reader.join(timeout=1)

    if timed_out.is_set():
        raise VideoToolError(f"ffmpeg timed out after {timeout_seconds}s")
    if process.returncode != 0:
        tail = " | ".join(stderr_tail) if stderr_tail else "ffmpeg failed"
        raise VideoToolError(tail)


def probe_video_size(
    source: str, *, ffprobe_path: str = "ffprobe", timeout_seconds: int = 30
) -> tuple[int, int] | None:
    """First video stream width/height via `ffprobe`, or None when unreadable.

    `source` may be a local path or a signed URL. Never raises; callers fall back to a
    default frame so styling can still be computed.
    """
    if not source or shutil.which(ffprobe_path) is None:
        return None
    try:
        completed = subprocess.run(
            [
                ffprobe_path,
                "-v",
                "error",
                "-select_streams",
                "v:0",
                "-show_entries",
                "stream=width,height",
                "-of",
                "csv=s=x:p=0",
                source,
            ],
            capture_output=True,
            timeout=timeout_seconds,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if completed.returncode != 0:
        return None
    text = completed.stdout.decode("utf-8", "replace").strip()
    if "x" not in text:
        return None
    width_text, _, height_text = text.partition("x")
    try:
        width, height = int(width_text), int(height_text)
    except ValueError:
        return None
    if width <= 0 or height <= 0:
        return None
    return width, height


def probe_has_audio(
    source: str, *, ffprobe_path: str = "ffprobe", timeout_seconds: int = 30
) -> bool:
    """True when the media has at least one audio stream. Never raises."""
    if not source or shutil.which(ffprobe_path) is None:
        return False
    try:
        completed = subprocess.run(
            [
                ffprobe_path,
                "-v",
                "error",
                "-select_streams",
                "a:0",
                "-show_entries",
                "stream=index",
                "-of",
                "csv=p=0",
                source,
            ],
            capture_output=True,
            timeout=timeout_seconds,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    return completed.returncode == 0 and bool(completed.stdout.strip())


class MediaToolkit:
    """Executes reviewer visual-context requests against one source video.

    `source` is anything FFmpeg can read: a local path, a `file://` URI, or (the
    production case) a short-lived HTTPS signed URL for the object in Cloud Storage.
    """

    def __init__(
        self,
        *,
        source: str,
        duration_ms: int,
        ffmpeg_path: str = "ffmpeg",
        window_seconds: int = 5,
        frame_max_width: int = 640,
        clip_max_height: int = 480,
        max_requests: int = 3,
        max_rounds: int = 2,
    ) -> None:
        if not source:
            raise ValueError("source is required")
        self.source = source
        self.duration_ms = max(0, int(duration_ms))
        self.ffmpeg_path = ffmpeg_path
        self.window_seconds = max(1, int(window_seconds))
        self.frame_max_width = max(160, int(frame_max_width))
        self.clip_max_height = max(144, int(clip_max_height))
        self.max_requests = max(1, int(max_requests))
        self.max_rounds = max(1, int(max_rounds))

    async def execute(
        self, name: str, arguments: dict[str, Any]
    ) -> tuple[MediaPart, ...]:
        """Run one model-requested tool call and return the media to show it.

        Raises `ValueError` for an unknown tool or missing timestamp; the provider
        records that as a failed call and the reviewer continues.
        """
        if name == TOOL_EXTRACT_FRAME:
            return (await self.extract_frame(_argument_ms(arguments)),)
        if name == TOOL_CUT_CLIP:
            return (await self.cut_clip(_argument_ms(arguments)),)
        raise ValueError(f"unknown tool: {name!r}")

    # ------------------------------------------------------------------ tools

    async def extract_frame(self, at_ms: int) -> MediaPart:
        """One JPEG still at `at_ms` (clamped into the video)."""
        timestamp = self._clamp(at_ms)
        args = [
            self.ffmpeg_path,
            "-hide_banner",
            "-loglevel",
            "error",
            "-ss",
            f"{timestamp / 1000:.3f}",
            "-i",
            self.source,
            "-frames:v",
            "1",
            "-vf",
            f"scale='min({self.frame_max_width},iw)':-2",
            "-f",
            "image2pipe",
            "-c:v",
            "mjpeg",
            "-q:v",
            "4",
            "pipe:1",
        ]
        data = await asyncio.to_thread(
            run_ffmpeg, args, timeout_seconds=_FRAME_TIMEOUT_SECONDS
        )
        return MediaPart(
            mime_type="image/jpeg",
            data=data,
            label=f"Frame at {format_timestamp(timestamp)}",
        )

    async def cut_clip(self, center_ms: int) -> MediaPart:
        """A short MP4 clip centred on `center_ms` (+/- `window_seconds`)."""
        center = self._clamp(center_ms)
        window_ms = self.window_seconds * 1000
        start = max(0, center - window_ms)
        # Clamp the tail to the video so the last seconds are not padded with black.
        end = min(self.duration_ms, center + window_ms) if self.duration_ms else center + window_ms
        duration = max(1, end - start) / 1000
        args = [
            self.ffmpeg_path,
            "-hide_banner",
            "-loglevel",
            "error",
            "-ss",
            f"{start / 1000:.3f}",
            "-i",
            self.source,
            "-t",
            f"{duration:.3f}",
            "-vf",
            f"scale=-2:'min({self.clip_max_height},ih)'",
            "-an",
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-crf",
            "30",
            "-pix_fmt",
            "yuv420p",
            "-movflags",
            "frag_keyframe+empty_moov+default_base_moof",
            "-f",
            "mp4",
            "pipe:1",
        ]
        data = await asyncio.to_thread(
            run_ffmpeg, args, timeout_seconds=_CLIP_TIMEOUT_SECONDS
        )
        return MediaPart(
            mime_type="video/mp4",
            data=data,
            label=(
                f"Clip {format_timestamp(start)}-{format_timestamp(round(end))} "
                f"(around {format_timestamp(center)})"
            ),
        )

    def _clamp(self, at_ms: int) -> int:
        return max(0, min(int(at_ms), self.duration_ms or int(at_ms)))


__all__ = [
    "ContextArtifactStore",
    "GcsContextArtifactStore",
    "MediaToolkit",
    "TOOL_CUT_CLIP",
    "TOOL_EXTRACT_FRAME",
    "TOOL_NAMES",
    "VideoToolError",
    "ffmpeg_available",
    "format_timestamp",
    "probe_duration_ms",
    "probe_video_size",
    "review_tool_specs",
    "run_ffmpeg",
    "run_ffmpeg_command",
    "run_ffmpeg_with_progress",
]
