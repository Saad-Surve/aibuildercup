"""Public-only, bounded creator collection. No cookies, logins or access-gate bypass."""

import json
import subprocess
import sys
from typing import Any
from urllib.parse import urlsplit

import requests
from bs4 import BeautifulSoup

_ALLOWED_PAGES = {
    "trak.in",
    "www.linkedin.com",
    "www.therodinhoods.com",
    "x.com",
    "www.instagram.com",
}


def youtube_metadata(url: str, *, flat: bool = False, limit: int = 12) -> dict[str, Any]:
    if urlsplit(url).hostname not in {"www.youtube.com", "youtube.com"}:
        raise ValueError("Only public YouTube URLs are supported")
    args = [
        sys.executable,
        "-m",
        "yt_dlp",
        "--skip-download",
        "--dump-single-json",
        "--socket-timeout",
        "10",
        "--retries",
        "0",
        "--extractor-retries",
        "0",
        "--no-warnings",
    ]
    if flat:
        args += ["--flat-playlist", "--playlist-end", str(min(30, limit))]
    else:
        args += ["--no-playlist"]
    try:
        result = subprocess.run([*args, url], capture_output=True, timeout=45, check=False)
    except subprocess.TimeoutExpired as exc:
        raise ValueError("Public metadata collection timed out") from exc
    if result.returncode or len(result.stdout) > 30_000_000:
        raise ValueError("Public video metadata unavailable")
    return dict(json.loads(result.stdout))


def public_bytes(url: str, *, hosts: set[str], cap: int = 2_000_000) -> bytes:
    parsed = urlsplit(url)
    if (
        parsed.scheme != "https"
        or parsed.hostname not in hosts
        or parsed.username
        or parsed.password
        or parsed.port not in {None, 443}
    ):
        raise ValueError("Unsupported public source URL")
    with requests.get(url, timeout=15, allow_redirects=False, stream=True) as response:
        if response.status_code != 200:
            raise ValueError(f"Public source returned HTTP {response.status_code}")
        data = bytearray()
        for chunk in response.iter_content(65536):
            data.extend(chunk)
            if len(data) > cap:
                raise ValueError("Public source exceeds byte cap")
    return bytes(data)


def captions(info: dict[str, Any]) -> tuple[str, str, str] | None:
    manual = info.get("subtitles") or {}
    automatic = info.get("automatic_captions") or {}
    language = str(info.get("language") or "hi")
    # Prefer the actual spoken language; do not silently substitute auto-translated English.
    for tracks, method in [(manual, "manual"), (automatic, "automatic")]:
        keys = [key for key in tracks if key == language or key == language + "-orig"]
        for key in sorted(keys, key=lambda value: not value.endswith("-orig")):
            formats = tracks[key]
            track = next((row for row in formats if row.get("ext") == "vtt"), None)
            if track:
                raw = public_bytes(track["url"], hosts={"www.youtube.com"}, cap=200 * 1024)
                return raw.decode("utf-8"), language, method
    return None


def public_page(url: str) -> dict[str, Any]:
    raw = public_bytes(url, hosts=_ALLOWED_PAGES)
    soup = BeautifulSoup(raw, "html.parser")
    if soup.title and any(
        marker in soup.title.get_text().lower()
        for marker in ["just a moment", "log in", "login", "sign in"]
    ):
        raise ValueError("Public page requires login or access challenge")
    if urlsplit(url).hostname == "www.linkedin.com":
        body = soup.select_one('[data-test-id="main-feed-activity-card__commentary"]')
        if body is None:
            body = soup.select_one(".attributed-text-segment-list__container")
        if body is None:
            raise ValueError("Authored post text unavailable")
        author = soup.select_one('[data-tracking-control-name="public_post_feed-actor-name"]')
        attribution = author.get_text(" ", strip=True) if author else ""
        if "Arun Prabhudesai" not in attribution:
            raise ValueError("Post author could not be verified")
        title = body.get_text(" ", strip=True).split("\n")[0][:140]
    else:
        body = soup.select_one("article") or soup.select_one("main")
        if body is None:
            raise ValueError("Article content unavailable")
        for element in body.select("script,style,nav,footer,form,.comments-area"):
            element.decompose()
        heading = body.select_one("h1")
        title = heading.get_text(" ", strip=True) if heading else "About Trakin Tech"
        attribution = "Trak.in editorial team"
    text = body.get_text("\n", strip=True)
    if len(text) < 100 or len(text.encode()) > 200 * 1024:
        raise ValueError("Insufficient or oversized authored text")
    return {"title": title, "text": text, "attribution": attribution, "raw": raw}
