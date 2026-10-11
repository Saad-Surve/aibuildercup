"""Collect a bounded public creator corpus with originals and explicit availability reports."""

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.providers.creator_media import download_youtube_thumbnail
from app.providers.creator_scraper import captions, public_page, youtube_metadata
from app.services.creator_import_service import prepare_import


def facets(title: str, *, short: bool = False) -> list[str]:
    """Explicit title-based navigation facets, never inferred creator claims."""
    lowered = title.lower()
    tags = ["shorts" if short else "long-form"]
    for name, tokens in {
        "buying advice": ["best", "deals", "under ₹", "sale"],
        "reviews": ["review", "unboxing", "impressions"],
        "tech news": ["ttn", "launch", "podcast"],
        "smartphones": ["phone", "iqoo", "vivo", "samsung", "poco", "pixel"],
        "computing": ["laptop", "macbook", "gpt", "gemini", "claude"],
    }.items():
        if any(token in lowered for token in tokens):
            tags.append(name)
    return tags


def collect(config: dict[str, Any], folder: Path) -> dict[str, Any]:
    if folder.exists() and (folder / "manifest.json").exists():
        raise ValueError("Use a new folder; collections are immutable snapshots")
    for name in ["raw", "texts", "thumbnails"]:
        (folder / name).mkdir(parents=True, exist_ok=True)
    fetched = datetime.now(UTC).isoformat()
    report: list[dict[str, Any]] = []
    items: list[dict[str, Any]] = []
    images = 0
    for suffix, limit in [("videos", 10), ("shorts", 4)]:
        channel = youtube_metadata(f"{config['channelUrl']}/{suffix}", flat=True, limit=limit)
        if channel.get("channel_id") != config["channelId"]:
            raise ValueError("Collected channel identity does not match the configured creator")
        (folder / "raw" / f"youtube-{suffix}.json").write_text(
            json.dumps(channel, ensure_ascii=False, indent=2)
        )
        for position, flat in enumerate(channel.get("entries", [])[:limit]):
            item_id = str(flat["id"])
            url = f"https://www.youtube.com/watch?v={item_id}"
            info = flat
            status = "unavailable"
            try:
                info = youtube_metadata(url)
                if info.get("channel_id") != config["channelId"]:
                    report.append(
                        {"url": url, "metadata": "excluded", "reason": "Channel mismatch"}
                    )
                    continue
                (folder / "raw" / f"{item_id}.json").write_text(
                    json.dumps(info, ensure_ascii=False, indent=2)
                )
            except (ValueError, TimeoutError) as error:
                info = flat
                report.append({"url": url, "metadata": "flat only", "reason": str(error)})
            language = info.get("language") or "und"
            text_file = f"texts/{item_id}.md"
            description = str(info.get("description") or "")
            # Fallback is genuine channel description/metadata, clearly labeled as such.
            text = f"# {info['title']}\n\n{description}".strip()
            (folder / text_file).write_text(text, encoding="utf-8")
            try:
                track = captions(info)
                if track:
                    raw, language, method = track
                    text_file = f"texts/{item_id}.vtt"
                    (folder / text_file).write_text(raw, encoding="utf-8")
                    status = method
            except Exception as error:
                report.append({"url": url, "captions": "unavailable", "reason": str(error)})
            thumbnail_file = None
            # Eight long-form + two Shorts; 10 real visual examples with distinct subjects.
            take_image = (suffix == "videos" and position < 8) or (
                suffix == "shorts" and position < 2
            )
            if take_image and images < 10:
                try:
                    candidates = [
                        t for t in info.get("thumbnails", []) if "i.ytimg.com" in t.get("url", "")
                    ]
                    thumb_url = max(candidates, key=lambda t: t.get("width") or 0)["url"]
                    image = download_youtube_thumbnail(thumb_url)
                    ext = {"image/jpeg": "jpg", "image/png": "png", "image/webp": "webp"}[
                        image.mime_type
                    ]
                    thumbnail_file = f"thumbnails/{item_id}.{ext}"
                    (folder / thumbnail_file).write_bytes(image.data)
                    images += 1
                except Exception as error:
                    report.append({"url": url, "thumbnail": "unavailable", "reason": str(error)})
            item = {
                "id": item_id,
                "kind": "video",
                "title": info["title"],
                "description": description[:10000],
                "tags": facets(info["title"], short=suffix == "shorts"),
                "textFile": text_file,
                "thumbnailFile": thumbnail_file,
                "url": url,
                "language": language,
                "platform": "youtube",
                "attribution": "Trakin Tech / Arun Prabhudesai",
                "contentType": f"{status} captions"
                if status != "unavailable"
                else "video description; captions unavailable",
                "collectionMethod": "yt-dlp; public metadata; title-based facets",
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
            date = info.get("upload_date")
            if date:
                item["publishedAt"] = (
                    datetime.strptime(date, "%Y%m%d").replace(tzinfo=UTC).isoformat()
                )
            items.append(item)
            report.append(
                {
                    "url": url,
                    "captions": status,
                    "language": language,
                    "thumbnail": bool(thumbnail_file),
                }
            )
            print(f"Collected {item_id}: {status} captions", flush=True)
    for index, url in enumerate([*config["writingUrls"], *config["availabilityUrls"]]):
        try:
            page = public_page(url)
            # Availability probes document restricted platforms; they are not authorship evidence.
            if url in config["availabilityUrls"]:
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
            report.append({"url": url, "status": "collected", "author": page["attribution"]})
        except Exception as error:
            report.append({"url": url, "status": "unavailable", "reason": str(error)})
        print(f"Checked writing source {index + 1}", flush=True)
    manifest = {
        "schemaVersion": 1,
        "bundleId": config["bundleId"],
        "creator": config["creator"],
        "items": items,
    }
    (folder / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2))
    (folder / "persona-user-supplied.json").write_text(json.dumps(config["creator"], indent=2))
    (folder / "collection-report.json").write_text(
        json.dumps(
            {
                "fetchedAt": fetched,
                "sources": report,
                "notes": "No generated transcripts, private analytics or login-gated material.",
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
