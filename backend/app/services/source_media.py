"""Stage a project source video for a local FFmpeg/FFprobe run.

Both the caption burn-in worker and the dubbing worker need a local, seekable file (or a
short-lived signed URL for very large sources) before they can probe and encode. A source that
fits the download budget is staged locally first: probing is then reliable (a *fragmented* MP4
makes a remote `ffprobe` scan the whole object and time out) and the encoder can seek instead of
re-reading fragments over the network. Larger sources stream from a signed URL so the temp disk
cannot fill up.
"""

import asyncio
import logging
import os

from app.config import Settings
from app.services.storage_service import StorageClient
from app.services.video_tools import VideoToolError, probe_video_metadata

logger = logging.getLogger(__name__)

_SOURCE_URL_TTL_SECONDS = 3600


async def stage_source(
    *,
    storage: StorageClient,
    source_path: str,
    tmpdir: str,
    settings: Settings,
    fallback_duration_ms: int,
) -> tuple[str, int, int, int]:
    """Return `(ffmpeg source, width, height, durationMs)` for a stored source object."""
    size: int | None
    try:
        size = await asyncio.to_thread(storage.object_size, source_path)
    except Exception:  # noqa: BLE001 - unknown size means "do not download"
        logger.warning("could not read the source size", exc_info=True)
        size = None

    local_path: str | None = None
    if size is not None and 0 < size <= settings.caption_max_source_download_bytes:
        extension = os.path.splitext(source_path)[1] or ".mp4"
        local_path = os.path.join(tmpdir, f"source{extension}")
        try:
            await asyncio.to_thread(storage.download_to_filename, source_path, local_path)
        except Exception:  # noqa: BLE001 - fall back to streaming the signed URL
            logger.warning("staging the source locally failed", exc_info=True)
            local_path = None

    source = local_path
    if source is None:
        try:
            source = await asyncio.to_thread(
                storage.signed_download_url, source_path, expires_seconds=_SOURCE_URL_TTL_SECONDS
            )
        except Exception as exc:  # noqa: BLE001 - surface a clear reason to the user
            logger.warning("could not access source video", exc_info=True)
            raise VideoToolError("Could not access the original video. Try again.") from exc

    metadata = await asyncio.to_thread(
        probe_video_metadata, source, ffprobe_path=settings.ffprobe_path
    )
    width, height, probed_duration = metadata or (1920, 1080, None)
    duration_ms = probed_duration or fallback_duration_ms
    return source, width, height, duration_ms
