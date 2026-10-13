"""Collect public YouTube "Most Replayed" curves and timed captions for the interest model.

Research data only. For each search result that passes the filters it stores the video's
metadata (id, channel, duration, views, the 100-point Most Replayed heatmap) and its
original-language auto-caption track with word timings. Only metadata and captions are
fetched, never video; the optional `asr` phase downloads audio only, transcribes it and
deletes it at once. Raw files stay under the gitignored `evals/interest/raw/`.

Two resumable phases, because captions come from a different endpoint than metadata:

    # 1. search and keep qualifying videos (metadata + heatmap)
    uv run --project backend python backend/scripts/interest_collect.py meta --target 450
    # 2. fetch timed caption lines for kept videos that do not have them yet
    uv run --project backend --with youtube-transcript-api \
        python backend/scripts/interest_collect.py subs
    # 2b. or, when YouTube blocks captions, transcribe locally (Apple silicon)
    uv run --project backend --with mlx-whisper \
        python backend/scripts/interest_collect.py asr
"""

import argparse
import json
import random
import sys
import time
from pathlib import Path
from typing import Any

import yt_dlp

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "evals" / "interest" / "raw"
META = RAW / "meta"
SUBS = RAW / "subs"

#: Talking-head and explainer niches that match the creators Resonance is built for.
#: (query, caption language)
QUERIES: list[tuple[str, str]] = [
    ("personal finance explained", "en"),
    ("how to invest for beginners", "en"),
    ("budgeting tips video essay", "en"),
    ("career advice interview tips", "en"),
    ("how to get a job in tech", "en"),
    ("productivity tips that actually work", "en"),
    ("home workout no equipment", "en"),
    ("nutrition science explained", "en"),
    ("fitness myths debunked", "en"),
    ("science explained documentary short", "en"),
    ("history explained video essay", "en"),
    ("tech explained how it works", "en"),
    ("smartphone review honest", "en"),
    ("laptop review after one month", "en"),
    ("AI tools explained", "en"),
    ("programming tutorial for beginners", "en"),
    ("cooking recipe easy dinner", "en"),
    ("travel vlog tips", "en"),
    ("startup founder story", "en"),
    ("psychology explained", "en"),
    ("study tips for students", "en"),
    ("small business ideas", "en"),
    ("product review unboxing", "en"),
    ("podcast clip interview", "en"),
    ("stock market explained hindi", "hi"),
    ("personal finance hindi", "hi"),
    ("career advice hindi", "hi"),
    ("science explained hindi", "hi"),
    ("tech review hindi", "hi"),
    ("study motivation hindi", "hi"),
]

MIN_SECONDS = 240
MAX_SECONDS = 1500
MIN_VIEWS = 100_000

_QUIET: dict[str, Any] = {
    "quiet": True,
    "no_warnings": True,
    "noprogress": True,
    "noplaylist": True,
    "skip_download": True,
}


def caption_key(info: dict[str, Any], language: str) -> str | None:
    """Key of the original ASR caption track in `language`, if YouTube lists one."""
    automatic = info.get("automatic_captions") or {}
    for key in (f"{language}-orig", language):
        if any(entry.get("ext") == "json3" for entry in automatic.get(key) or []):
            return key
    return None


def rejection(info: dict[str, Any], language: str) -> str | None:
    """Why a video is rejected, or None when it qualifies."""
    duration = info.get("duration") or 0
    if not MIN_SECONDS <= duration <= MAX_SECONDS:
        return "duration"
    if (info.get("view_count") or 0) < MIN_VIEWS:
        return "views"
    if info.get("live_status") not in (None, "not_live", "was_live"):
        return "live"
    if len(info.get("heatmap") or []) < 50:
        return "no_heatmap"
    if caption_key(info, language) is None:
        return "no_captions"
    return None


def collect_meta(args: argparse.Namespace) -> None:
    META.mkdir(parents=True, exist_ok=True)
    have = {path.stem for path in META.glob("*.json")}
    per_channel: dict[str, int] = {}
    for path in META.glob("*.json"):
        channel = json.loads(path.read_text(encoding="utf-8")).get("channel_id") or ""
        per_channel[channel] = per_channel.get(channel, 0) + 1
    rejected: dict[str, int] = {}

    flat = yt_dlp.YoutubeDL({**_QUIET, "extract_flat": True})
    full = yt_dlp.YoutubeDL(_QUIET)
    queries = QUERIES[:]
    random.Random(7).shuffle(queries)
    for query, language in queries:
        if len(have) >= args.target:
            break
        try:
            listing = flat.extract_info(f"ytsearch{args.per_query}:{query}", download=False)
        except Exception as exc:  # noqa: BLE001 - one failed search must not end the run
            print(f"search failed for {query!r}: {exc}", file=sys.stderr)
            continue
        for entry in (listing or {}).get("entries") or []:
            video_id = entry.get("id")
            if not video_id or video_id in have or len(have) >= args.target:
                continue
            duration = entry.get("duration") or 0
            if duration and not MIN_SECONDS <= duration <= MAX_SECONDS:
                continue
            channel_id = entry.get("channel_id") or ""
            if channel_id and per_channel.get(channel_id, 0) >= args.max_per_channel:
                continue
            try:
                info = full.extract_info(
                    f"https://www.youtube.com/watch?v={video_id}", download=False
                )
            except Exception as exc:  # noqa: BLE001
                print(f"skip {video_id}: {str(exc)[:120]}", file=sys.stderr)
                continue
            time.sleep(args.sleep)
            channel_id = info.get("channel_id") or channel_id
            reason = rejection(info, language)
            if reason is None and per_channel.get(channel_id, 0) >= args.max_per_channel:
                reason = "channel_cap"
            if reason is not None:
                rejected[reason] = rejected.get(reason, 0) + 1
                continue
            meta = {
                "id": video_id,
                "title": info.get("title"),
                "channel_id": channel_id,
                "channel": info.get("channel"),
                "duration": info.get("duration"),
                "view_count": info.get("view_count"),
                "upload_date": info.get("upload_date"),
                "language": language,
                "caption_track": caption_key(info, language),
                "query": query,
                "heatmap": info.get("heatmap"),
                "chapters": info.get("chapters"),
            }
            (META / f"{video_id}.json").write_text(json.dumps(meta), encoding="utf-8")
            have.add(video_id)
            per_channel[channel_id] = per_channel.get(channel_id, 0) + 1
            print(
                f"[{len(have)}] {video_id} {language} {info.get('duration')}s {query!r}",
                flush=True,
            )
    print(json.dumps({"videos": len(have), "rejected": rejected}, indent=2), flush=True)


def collect_subs(args: argparse.Namespace) -> None:
    """Fetch timed caption lines through the transcript API.

    YouTube throttles yt-dlp's caption endpoint per IP; the transcript API is not throttled
    the same way. It returns caption lines (text, start, duration), not word timings,
    which is enough: training spreads words over segments exactly as inference does.
    Auto-generated tracks are preferred because they match a speech-to-text transcript.
    """
    from youtube_transcript_api import YouTubeTranscriptApi

    SUBS.mkdir(parents=True, exist_ok=True)
    api = YouTubeTranscriptApi()
    pending = [
        json.loads(path.read_text(encoding="utf-8"))
        for path in sorted(META.glob("*.json"))
        if not (SUBS / f"{path.stem}.json3").exists()
        and not (SUBS / f"{path.stem}.lines.json").exists()
    ]
    print(f"{len(pending)} videos need captions", flush=True)
    fetched = failed = blocks = 0
    for meta in pending:
        video_id = meta["id"]
        language = meta.get("language") or "en"
        # The search language is only a hint: a video found by an English query may be
        # spoken in Hindi, and yt-dlp then lists YouTube's machine translation as "en".
        # Only the original-language ASR track is a real transcript of the audio.
        preferred = [language, *(code for code in ("en", "hi") if code != language)]
        while True:
            try:
                listing = api.list(video_id)
                try:
                    transcript = listing.find_generated_transcript(preferred)
                except Exception:  # noqa: BLE001 - fall back to a creator-made track
                    transcript = listing.find_transcript(preferred)
                lines = [
                    {"text": snippet.text, "start": snippet.start, "duration": snippet.duration}
                    for snippet in transcript.fetch().snippets
                ]
                blocks = 0
                break
            except Exception as exc:  # noqa: BLE001
                name = type(exc).__name__
                if name in ("IpBlocked", "RequestBlocked", "TooManyRequests"):
                    blocks += 1
                    if blocks > args.max_blocks:
                        print("still blocked; stopping. Re-run later to resume.", flush=True)
                        print(f"done: {fetched} fetched, {failed} failed", flush=True)
                        return
                    wait = min(3600, args.backoff * 2 ** (blocks - 1))
                    print(f"{name} on {video_id}; waiting {wait:.0f}s", flush=True)
                    time.sleep(wait)
                    continue
                lines = []
                failed += 1
                print(f"skip {video_id}: {name}", file=sys.stderr, flush=True)
                break
        if not lines:
            time.sleep(args.sleep)
            continue
        payload = {
            "generated": transcript.is_generated,
            "language": transcript.language_code,
            "lines": lines,
        }
        (SUBS / f"{video_id}.lines.json").write_text(json.dumps(payload), encoding="utf-8")
        if transcript.language_code != language:
            meta["language"] = transcript.language_code
            meta["caption_track"] = transcript.language_code
            (META / f"{video_id}.json").write_text(json.dumps(meta), encoding="utf-8")
        fetched += 1
        print(f"[{fetched}/{len(pending)}] {video_id}", flush=True)
        time.sleep(args.sleep + random.uniform(0, args.sleep / 2))
    print(f"done: {fetched} fetched, {failed} failed", flush=True)


def collect_asr(args: argparse.Namespace) -> None:
    """Transcribe kept videos locally when YouTube blocks its caption endpoints.

    Downloads the audio track only, transcribes it with Whisper on Apple silicon (MLX),
    stores the timed segments in the same `lines` format as `subs`, and deletes the audio
    at once. Nothing but the timed transcript is kept.
    """
    import tempfile

    import mlx_whisper  # type: ignore[import-not-found]

    SUBS.mkdir(parents=True, exist_ok=True)
    pending = [
        json.loads(path.read_text(encoding="utf-8"))
        for path in sorted(META.glob("*.json"))
        if not (SUBS / f"{path.stem}.lines.json").exists()
    ]
    # A second worker can take the list from the other end; they meet in the middle.
    if args.reverse:
        pending.reverse()
    pending = pending[: args.limit]
    print(f"{len(pending)} videos to transcribe with {args.model}", flush=True)
    done = failed = 0
    with tempfile.TemporaryDirectory() as workdir:
        for meta in pending:
            video_id = meta["id"]
            if (SUBS / f"{video_id}.lines.json").exists():
                continue
            options = {
                **_QUIET,
                "skip_download": False,
                "format": "bestaudio[ext=m4a]/bestaudio",
                "outtmpl": str(Path(workdir) / "%(id)s.%(ext)s"),
            }
            started = time.monotonic()
            try:
                with yt_dlp.YoutubeDL(options) as ydl:
                    ydl.extract_info(f"https://www.youtube.com/watch?v={video_id}", download=True)
                audio = next(Path(workdir).glob(f"{video_id}.*"))
                # Not conditioning on the previous window stops one bad segment from
                # cascading into a repetition loop, a known Whisper failure on long audio.
                result = mlx_whisper.transcribe(
                    str(audio),
                    path_or_hf_repo=args.model,
                    condition_on_previous_text=False,
                )
            except Exception as exc:  # noqa: BLE001
                failed += 1
                print(f"skip {video_id}: {str(exc)[:120]}", file=sys.stderr, flush=True)
                continue
            finally:
                for leftover in Path(workdir).glob(f"{video_id}.*"):
                    leftover.unlink()
            lines = [
                {
                    "text": str(segment["text"]).strip(),
                    "start": float(segment["start"]),
                    "duration": float(segment["end"]) - float(segment["start"]),
                }
                for segment in result.get("segments") or []
                if str(segment.get("text") or "").strip()
            ]
            language = str(result.get("language") or meta.get("language") or "")
            payload = {"generated": True, "source": "whisper", "language": language, "lines": lines}
            (SUBS / f"{video_id}.lines.json").write_text(json.dumps(payload), encoding="utf-8")
            if language and language != meta.get("language"):
                meta["language"] = language
                (META / f"{video_id}.json").write_text(json.dumps(meta), encoding="utf-8")
            done += 1
            print(
                f"[{done}/{len(pending)}] {video_id} {language} {time.monotonic() - started:.0f}s",
                flush=True,
            )
    print(f"done: {done} transcribed, {failed} failed", flush=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    phases = parser.add_subparsers(dest="phase", required=True)
    meta = phases.add_parser("meta", help="Search and keep qualifying videos.")
    meta.add_argument("--target", type=int, default=450, help="Stop after this many videos.")
    meta.add_argument("--per-query", type=int, default=40, help="Search results per query.")
    meta.add_argument("--max-per-channel", type=int, default=3)
    meta.add_argument("--sleep", type=float, default=1.0, help="Seconds between videos.")
    subs = phases.add_parser("subs", help="Fetch captions for kept videos.")
    subs.add_argument("--sleep", type=float, default=25.0, help="Seconds between videos.")
    subs.add_argument("--backoff", type=float, default=600.0, help="First block wait, seconds.")
    subs.add_argument("--max-blocks", type=int, default=8)
    asr = phases.add_parser("asr", help="Transcribe kept videos locally (audio is deleted).")
    asr.add_argument("--model", default="mlx-community/whisper-large-v3-turbo")
    asr.add_argument("--limit", type=int, default=400)
    asr.add_argument("--reverse", action="store_true", help="Work from the end of the list.")
    args = parser.parse_args()
    if args.phase == "meta":
        collect_meta(args)
    elif args.phase == "subs":
        collect_subs(args)
    else:
        collect_asr(args)


if __name__ == "__main__":
    main()
