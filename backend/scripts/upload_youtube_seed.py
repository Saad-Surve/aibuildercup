"""Compact a local `fixtures/seed/youtube` channel into one JSON and upload it to GCS.

The studio's creator-content features (style/RAG, transcripts, thumbnail references) are built from
a connected YouTube channel. A fresh account has little content, so for the demo we seed from a
public **CC BY** channel gathered under `fixtures/seed/youtube` (see its README/ATTRIBUTION).

This writes `seed/youtube/<slug>.json` into the media bucket: one record per video with the
metadata the app stores plus the transcript text, so the API can load it without the (gitignored)
local dataset. Thumbnails stay as their public YouTube CDN URL.

Usage (from `backend/`):

    uv run python scripts/upload_youtube_seed.py --channels lawrencesystems --limit 60
    uv run python scripts/upload_youtube_seed.py --channels all --limit 60
"""

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

# Make `app` importable whether the script is run from `backend/` or elsewhere.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.channel_content_service import _srt_to_text
from app.services.storage_service import get_storage_client

# slug -> folder under fixtures/seed/youtube
CHANNELS: dict[str, str] = {
    "lawrencesystems": "LawrenceSystems",
    "psych2go": "Psych2Go",
    "moxieboosted": "MoxieBoosted",
    "thehumanistreport": "TheHumanistReport",
}

_SEED_PREFIX = "seed/youtube"
_DESCRIPTION_MAX = 1500


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _transcript(channel_dir: Path, video_id: str) -> str:
    """Prefer the channel's own VTT (timestamped), then the corpus plain text."""
    data_dir = channel_dir / "data"
    for name in (f"{video_id}.en.vtt", f"{video_id}.en-orig.vtt"):
        candidate = data_dir / name
        if candidate.exists():
            return _srt_to_text(candidate.read_text(encoding="utf-8", errors="replace"))
    if data_dir.exists():
        for candidate in sorted(data_dir.glob(f"{video_id}.*.vtt")):
            return _srt_to_text(candidate.read_text(encoding="utf-8", errors="replace"))
    corpus = _repo_root() / "fixtures/seed/youtube/transcripts" / f"{video_id}.txt"
    if corpus.exists():
        return corpus.read_text(encoding="utf-8", errors="replace").strip()
    return ""


def _item(record: dict[str, Any], channel_dir: Path, *, transcript_max: int) -> dict[str, Any]:
    video_id = str(record.get("id") or "").strip()
    published = None
    timestamp = record.get("timestamp")
    if isinstance(timestamp, (int, float)) and timestamp > 0:
        published = datetime.fromtimestamp(timestamp, tz=UTC).isoformat()
    thumbnail = record.get("thumbnail") or (
        f"https://i.ytimg.com/vi/{video_id}/maxresdefault.jpg"
    )
    return {
        "videoId": video_id,
        "title": str(record.get("title") or "")[:300],
        "description": str(record.get("description") or "")[:_DESCRIPTION_MAX],
        "tags": [str(tag) for tag in (record.get("tags") or [])][:30],
        "publishedAt": published,
        "durationSeconds": record.get("duration"),
        "viewCount": record.get("view_count"),
        "likeCount": record.get("like_count"),
        "commentCount": record.get("comment_count"),
        "thumbnailUrl": thumbnail,
        "language": "en",
        "transcript": _transcript(channel_dir, video_id)[:transcript_max],
    }


def build_channel(slug: str, folder: str, *, limit: int, transcript_max: int) -> dict[str, Any]:
    channel_dir = _repo_root() / "fixtures/seed/youtube" / folder
    index = channel_dir / "index.jsonl"
    if not index.exists():
        raise SystemExit(f"Missing {index}")
    items: list[dict[str, Any]] = []
    channel_name = folder
    with index.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not str(record.get("id") or "").strip():
                continue
            if not items:
                channel_name = str(record.get("channel") or folder)
            items.append(_item(record, channel_dir, transcript_max=transcript_max))
            if limit and len(items) >= limit:
                break
    return {
        "channel": channel_name,
        "slug": slug,
        "source": "PleIAs/YouTube-Commons (CC BY)",
        "license": "Creative Commons Attribution license (reuse allowed)",
        "attribution": (
            'Each video: "<title>" by <channel> — '
            "https://www.youtube.com/watch?v=<id> — licensed CC BY"
        ),
        "generatedAt": datetime.now(UTC).isoformat(),
        "itemCount": len(items),
        "items": items,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--channels",
        default="lawrencesystems",
        help="comma-separated slugs, or 'all'",
    )
    parser.add_argument("--limit", type=int, default=60, help="videos per channel (0 = all)")
    parser.add_argument("--transcript-max", type=int, default=6000)
    args = parser.parse_args()

    slugs = (
        list(CHANNELS)
        if args.channels == "all"
        else [slug.strip() for slug in args.channels.split(",") if slug.strip()]
    )
    unknown = [slug for slug in slugs if slug not in CHANNELS]
    if unknown:
        raise SystemExit(f"Unknown channel(s): {', '.join(unknown)}. Known: {', '.join(CHANNELS)}")

    storage = get_storage_client()
    for slug in slugs:
        channel_dir = _repo_root() / "fixtures/seed/youtube" / CHANNELS[slug]
        if not (channel_dir / "index.jsonl").exists():
            print(f"{slug}: skipped (no index.jsonl — not fully gathered)")
            continue
        payload = build_channel(
            slug, CHANNELS[slug], limit=args.limit, transcript_max=args.transcript_max
        )
        object_path = f"{_SEED_PREFIX}/{slug}.json"
        body = json.dumps(payload, ensure_ascii=False)
        storage.upload_text(object_path, body, content_type="application/json")
        with_transcripts = sum(1 for item in payload["items"] if item["transcript"])
        print(
            f"{slug}: {payload['itemCount']} videos "
            f"({with_transcripts} with transcript) -> gs://<media-bucket>/{object_path} "
            f"({len(body) // 1024} KB)"
        )


if __name__ == "__main__":
    sys.exit(main())
