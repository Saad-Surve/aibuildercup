"""Collect a bounded public creator corpus with originals and explicit availability reports."""

import argparse
import json
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.providers.creator_media import download_youtube_thumbnail
from app.providers.creator_scraper import captions, public_page, youtube_metadata
from app.services.creator_import_service import prepare_import


def facets(
    title: str, rules: dict[str, list[str]] | None = None, *, short: bool = False
) -> list[str]:
    """Explicit title-based navigation facets, never inferred creator claims."""
    lowered = title.casefold()
    tags = ["shorts" if short else "long-form"]
    configured = rules or {
        "buying advice": ["best", "deals", "under ₹", "sale"],
        "reviews": ["review", "unboxing", "impressions"],
        "tech news": ["ttn", "launch", "podcast"],
        "smartphones": ["phone", "iqoo", "vivo", "samsung", "poco", "pixel"],
        "computing": ["laptop", "macbook", "gpt", "gemini", "claude"],
    }
    for name, tokens in configured.items():
        if any(token.casefold() in lowered for token in tokens):
            tags.append(name)
    return tags


def _timestamp(seconds: float) -> str:
    millis = max(0, round(seconds * 1000))
    hours, remainder = divmod(millis, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    secs, millis = divmod(remainder, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}.{millis:03d}"


def _local_whisper(url: str, item_id: str, model: str) -> tuple[str, str]:
    """Download one audio track, transcribe through MLX Whisper, and discard the audio."""
    import mlx_whisper  # type: ignore[import-not-found]
    import yt_dlp

    with tempfile.TemporaryDirectory() as workdir:
        options: dict[str, Any] = {
            "quiet": True,
            "no_warnings": True,
            "noprogress": True,
            "noplaylist": True,
            "format": "bestaudio[ext=m4a]/bestaudio",
            "outtmpl": str(Path(workdir) / "%(id)s.%(ext)s"),
        }
        with yt_dlp.YoutubeDL(options) as ydl:
            ydl.extract_info(url, download=True)
        audio = next(Path(workdir).glob(f"{item_id}.*"))
        result = mlx_whisper.transcribe(
            str(audio), path_or_hf_repo=model, condition_on_previous_text=False
        )
    segments = [
        segment
        for segment in result.get("segments") or []
        if str(segment.get("text") or "").strip()
    ]
    if not segments:
        raise ValueError("Local Whisper returned no transcript segments")
    blocks = ["WEBVTT", ""]
    for index, segment in enumerate(segments, start=1):
        blocks.extend(
            [
                str(index),
                f"{_timestamp(float(segment['start']))} --> {_timestamp(float(segment['end']))}",
                str(segment["text"]).strip(),
                "",
            ]
        )
    return "\n".join(blocks), str(result.get("language") or "und")


def _video_sources(config: dict[str, Any], folder: Path) -> list[tuple[str, int, str]]:
    explicit = config.get("videoUrls")
    if explicit:
        return [("videos", index, str(url)) for index, url in enumerate(explicit)]
    sources: list[tuple[str, int, str]] = []
    for suffix, limit in [("videos", 10), ("shorts", 4)]:
        channel = youtube_metadata(f"{config['channelUrl']}/{suffix}", flat=True, limit=limit)
        if channel.get("channel_id") != config["channelId"]:
            raise ValueError("Collected channel identity does not match the configured creator")
        (folder / "raw" / f"youtube-{suffix}.json").write_text(
            json.dumps(channel, ensure_ascii=False, indent=2)
        )
        for position, flat in enumerate(channel.get("entries", [])[:limit]):
            sources.append(
                (suffix, position, f"https://www.youtube.com/watch?v={flat['id']}")
            )
    return sources


def _excluded_term(config: dict[str, Any], *values: str) -> str | None:
    haystack = "\n".join(values).casefold()
    return next(
        (str(term) for term in config.get("excludedTerms", []) if str(term).casefold() in haystack),
        None,
    )


def collect(config: dict[str, Any], folder: Path) -> dict[str, Any]:
    if folder.exists() and (folder / "manifest.json").exists():
        raise ValueError("Use a new folder; collections are immutable snapshots")
    for name in ["raw", "texts", "thumbnails"]:
        (folder / name).mkdir(parents=True, exist_ok=True)
    fetched = datetime.now(UTC).isoformat()
    report: list[dict[str, Any]] = []
    items: list[dict[str, Any]] = []
    images = 0
    caption_attempts = 0
    asr_attempts = 0
    thumbnail_limit = int(config.get("thumbnailLimit", 10))
    item_limit = int(config.get("itemLimit", 30))
    caption_limit = int(config.get("captionRequestLimit", 30))
    asr_limit = int(config.get("localWhisperLimit", item_limit))
    excluded_ids = {str(key): str(value) for key, value in config.get("excludedIds", {}).items()}
    required_license = config.get("requiredLicense")
    published_before = config.get("publishedBefore")
    before_date = datetime.fromisoformat(str(published_before)).date() if published_before else None
    sources = _video_sources(config, folder)
    for suffix, _position, url in sources:
        item_id = url.rsplit("=", 1)[-1]
        if item_id in excluded_ids:
            report.append(
                {"url": url, "status": "excluded", "reason": excluded_ids[item_id]}
            )
            continue
        try:
            info = youtube_metadata(url)
        except (ValueError, TimeoutError) as error:
            report.append({"url": url, "status": "excluded", "reason": str(error)})
            continue
        if info.get("channel_id") != config["channelId"]:
            report.append({"url": url, "status": "excluded", "reason": "Channel mismatch"})
            continue
        (folder / "raw" / f"{item_id}.json").write_text(
            json.dumps(info, ensure_ascii=False, indent=2)
        )
        license_name = str(info.get("license") or "")
        if required_license and license_name != required_license:
            report.append(
                {
                    "url": url,
                    "status": "excluded",
                    "reason": f"License is {license_name or 'not declared'}, not required CC BY",
                    "license": license_name or None,
                }
            )
            continue
        date = info.get("upload_date")
        if before_date and (
            not date or datetime.strptime(str(date), "%Y%m%d").date() >= before_date
        ):
            report.append(
                {
                    "url": url,
                    "status": "excluded",
                    "reason": f"Published on or after exclusive cutoff {before_date.isoformat()}",
                    "publishedAt": date,
                }
            )
            continue
        description = str(info.get("description") or "")
        term = _excluded_term(config, str(info.get("title") or ""), description)
        if term:
            report.append(
                {"url": url, "status": "excluded", "reason": f"Matched excluded phrase: {term}"}
            )
            continue
        if len(items) >= item_limit:
            report.append({"url": url, "status": "excluded", "reason": "Item limit reached"})
            continue
        language = str(info.get("language") or "und")
        text_file = f"texts/{item_id}.md"
        text = f"# {info['title']}\n\n{description}".strip()
        status = "description"
        if caption_attempts < caption_limit:
            caption_attempts += 1
            try:
                track = captions(info)
                if track:
                    text, language, status = track
                    text_file = f"texts/{item_id}.vtt"
            except Exception as error:  # noqa: BLE001 - report each public endpoint failure.
                report.append({"url": url, "captions": "unavailable", "reason": str(error)})
        if (
            status == "description"
            and config.get("localWhisperFallback")
            and asr_attempts < asr_limit
        ):
            asr_attempts += 1
            try:
                text, language = _local_whisper(
                    url,
                    item_id,
                    str(config.get("whisperModel", "mlx-community/whisper-large-v3-turbo")),
                )
                text_file = f"texts/{item_id}.vtt"
                status = "local Whisper"
            except Exception as error:  # noqa: BLE001 - description fallback is intentional.
                report.append({"url": url, "localWhisper": "unavailable", "reason": str(error)})
        term = _excluded_term(config, text)
        if term:
            report.append(
                {
                    "url": url,
                    "status": "excluded",
                    "reason": f"Transcript matched excluded phrase: {term}",
                }
            )
            continue
        (folder / text_file).write_text(text, encoding="utf-8")
        thumbnail_file = None
        if images < thumbnail_limit:
            try:
                candidates = [
                    thumb
                    for thumb in info.get("thumbnails", [])
                    if "i.ytimg.com" in thumb.get("url", "")
                ]
                thumb_url = max(candidates, key=lambda thumb: thumb.get("width") or 0)["url"]
                image = download_youtube_thumbnail(thumb_url)
                ext = {"image/jpeg": "jpg", "image/png": "png", "image/webp": "webp"}[
                    image.mime_type
                ]
                thumbnail_file = f"thumbnails/{item_id}.{ext}"
                (folder / thumbnail_file).write_bytes(image.data)
                images += 1
            except Exception as error:  # noqa: BLE001 - a thumbnail is optional.
                report.append({"url": url, "thumbnail": "unavailable", "reason": str(error)})
        attribution = str(config.get("attribution") or "").strip()
        item = {
            "id": item_id,
            "kind": "video",
            "title": info["title"],
            "description": description[:10000],
            "tags": facets(info["title"], config.get("facets"), short=suffix == "shorts"),
            "textFile": text_file,
            "thumbnailFile": thumbnail_file,
            "url": url,
            "language": language,
            "platform": "youtube",
            "attribution": f"{attribution}; {url}" if attribution else url,
            "license": license_name or None,
            "contentType": (
                f"{status} captions"
                if status in {"manual", "automatic"}
                else "locally generated Whisper transcript"
                if status == "local Whisper"
                else "video description; captions and local transcript unavailable"
            ),
            "collectionMethod": (
                "yt-dlp public metadata and audio; local MLX Whisper; title-based facets"
                if status == "local Whisper"
                else "yt-dlp public metadata; title-based facets"
                if status == "description"
                else "yt-dlp public metadata; YouTube captions; title-based facets"
            ),
            "fetchedAt": fetched,
            "durationSeconds": int(info.get("duration") or 0),
        }
        for key in ["viewCount", "likeCount", "commentCount"]:
            value = info.get(
                {
                    "viewCount": "view_count",
                    "likeCount": "like_count",
                    "commentCount": "comment_count",
                }[key]
            )
            if value is not None:
                item[key] = value
        if date:
            item["publishedAt"] = (
                datetime.strptime(str(date), "%Y%m%d").replace(tzinfo=UTC).isoformat()
            )
        items.append(item)
        report.append(
            {
                "url": url,
                "status": "included",
                "license": license_name or None,
                "transcriptMethod": status,
                "language": language,
                "thumbnail": bool(thumbnail_file),
            }
        )
        print(f"Collected {item_id}: {status}", flush=True)
    for index, url in enumerate(
        [*config.get("writingUrls", []), *config.get("availabilityUrls", [])]
    ):
        try:
            page = public_page(url)
            if url in config.get("availabilityUrls", []):
                report.append({"url": url, "status": "public page only; not imported"})
                continue
            item_id = f"writing-{index}"
            (folder / "raw" / f"{item_id}.html").write_bytes(page["raw"])
            text_file = f"texts/{item_id}.md"
            (folder / text_file).write_text(page["text"], encoding="utf-8")
            linkedin = "linkedin.com" in url
            items.append(
                {
                    "id": item_id,
                    "kind": "post" if linkedin else "article",
                    "title": page["title"],
                    "textFile": text_file,
                    "url": url,
                    "platform": "linkedin" if linkedin else "website",
                    "language": "en",
                    "attribution": page["attribution"],
                    "collectionMethod": "public HTML",
                    "contentType": "authored post" if linkedin else "brand biography",
                    "fetchedAt": fetched,
                    "tags": ["creator business" if linkedin else "identity"],
                }
            )
            report.append({"url": url, "status": "included", "author": page["attribution"]})
        except Exception as error:  # noqa: BLE001 - availability is recorded, not hidden.
            report.append({"url": url, "status": "unavailable", "reason": str(error)})
        print(f"Checked writing source {index + 1}", flush=True)
    manifest = {
        "schemaVersion": 1,
        "bundleId": config["bundleId"],
        "creator": config["creator"],
        "items": items,
    }
    (folder / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2))
    (folder / "persona-user-supplied.json").write_text(
        json.dumps(config["creator"], indent=2)
    )
    included = sum(row.get("status") == "included" for row in report)
    excluded = sum(row.get("status") == "excluded" for row in report)
    (folder / "collection-report.json").write_text(
        json.dumps(
            {
                "fetchedAt": fetched,
                "included": included,
                "excluded": excluded,
                "captionRequests": caption_attempts,
                "localWhisperAttempts": asr_attempts,
                "sources": report,
                "notes": (
                    "Public metadata and captions only; local Whisper is used only as the "
                    "declared fallback. Description-only items are labeled in the manifest."
                ),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return prepare_import(folder).summary()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("config", type=Path)
    parser.add_argument("folder", type=Path)
    args = parser.parse_args()
    print(json.dumps(collect(json.loads(args.config.read_text()), args.folder), indent=2))


if __name__ == "__main__":
    main()
