"""Bounded downloads of connector-provided YouTube thumbnails."""

from urllib.parse import urlparse

import requests

from app.providers.base import MediaPart


def download_youtube_thumbnail(url: str) -> MediaPart:
    parsed = urlparse(url)
    if (
        parsed.scheme != "https"
        or parsed.hostname not in {"i.ytimg.com", "img.youtube.com"}
        or parsed.username
        or parsed.password
        or parsed.port not in {None, 443}
    ):
        raise ValueError("Unsupported thumbnail host")
    with requests.get(url, timeout=10, allow_redirects=False, stream=True) as response:
        response.raise_for_status()
        if response.status_code != 200:
            raise ValueError("Thumbnail redirects are not supported")
        content = bytearray()
        for chunk in response.iter_content(65536):
            content.extend(chunk)
            if len(content) > 5_000_000:
                raise ValueError("Thumbnail exceeds size cap")
        mime = response.headers.get("Content-Type", "image/jpeg").split(";")[0]
    if not content or mime not in {"image/jpeg", "image/png", "image/webp"}:
        raise ValueError("Unsupported thumbnail image")
    return MediaPart(mime_type=mime, data=bytes(content))
