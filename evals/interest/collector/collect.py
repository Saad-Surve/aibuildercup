# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "yt-dlp>=2026.8.19",
#     "curl_cffi>=0.11",
#     "youtube-transcript-api>=1.2",
#     "faster-whisper>=1.1",
#     "av<15",  # PyAV 15 dropped an argument faster-whisper's decoder still passes
# ]
# ///
"""Overnight collector for the Resonance interest model (Windows, macOS or Linux).

Collects public YouTube videos' "Most Replayed" graphs plus timed transcripts and writes them
in the exact format `backend/scripts/interest_train.py` reads. Run it with `run.bat` (Windows)
or `uv run collect.py` anywhere. It is resumable: stop it any time and run it again.

Per video it stores only metadata, the replay graph and a timed transcript. When YouTube's own
captions are blocked, it downloads the audio track only, transcribes it locally with
faster-whisper, and deletes the audio immediately.

Output goes to `evals/interest/raw/meta` and `raw/subs`, where `interest_train.py` reads it.
`--zip-only` packs meta, subs and Gemini signals into `interest_data_<date>.zip` to send back.
"""

import argparse
import json
import logging
import random
import shutil
import sys
import tempfile
import time
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Any

import yt_dlp

HERE = Path(__file__).resolve().parent
#: Inside the repo this is `evals/interest/raw/`, which `interest_train.py` reads directly.
OUT = HERE.parent / "raw"
META = OUT / "meta"
SUBS = OUT / "subs"
SIGNALS = OUT / "signals"

#: Talking-head and explainer niches (query, expected language). The language is a hint
#: only: the original-language ASR track decides.
QUERIES: list[tuple[str, str]] = [
    ("personal finance explained", "en"),
    ("how to invest for beginners", "en"),
    ("money mistakes to avoid", "en"),
    ("budgeting tips video essay", "en"),
    ("career advice interview tips", "en"),
    ("how to get a job in tech", "en"),
    ("resume tips that work", "en"),
    ("productivity tips that actually work", "en"),
    ("how I study effectively", "en"),
    ("home workout no equipment", "en"),
    ("nutrition science explained", "en"),
    ("fitness myths debunked", "en"),
    ("science explained", "en"),
    ("history explained video essay", "en"),
    ("geography explained", "en"),
    ("tech explained how it works", "en"),
    ("smartphone review honest", "en"),
    ("laptop review after one month", "en"),
    ("AI tools explained", "en"),
    ("programming tutorial for beginners", "en"),
    ("cooking recipe easy dinner", "en"),
    ("travel vlog tips", "en"),
    ("startup founder story", "en"),
    ("business case study explained", "en"),
    ("psychology explained", "en"),
    ("philosophy explained simply", "en"),
    ("small business ideas", "en"),
    ("product review unboxing", "en"),
    ("car review walkaround", "en"),
    ("podcast clip interview", "en"),
    ("movie explained ending", "en"),
    ("book summary animated", "en"),
    ("stock market explained hindi", "hi"),
    ("personal finance hindi", "hi"),
    ("career advice hindi", "hi"),
    ("science explained hindi", "hi"),
    ("tech review hindi", "hi"),
    ("study motivation hindi", "hi"),
    ("business case study hindi", "hi"),
    ("history explained hindi", "hi"),
]

MIN_SECONDS = 240
MAX_SECONDS = 1500
MIN_VIEWS = 100_000
BLOCKED = ("IpBlocked", "RequestBlocked", "TooManyRequests")

_QUIET: dict[str, Any] = {
    "quiet": True,
    "no_warnings": True,
    "noprogress": True,
    "noplaylist": True,
    "skip_download": True,
}

log = logging.getLogger("collector")


def keep_awake() -> None:
    """Stop Windows from sleeping while the collector runs (no-op elsewhere)."""
    if sys.platform != "win32":
        return
    import ctypes

    es_continuous, es_system_required = 0x80000000, 0x00000001
    ctypes.windll.kernel32.SetThreadExecutionState(es_continuous | es_system_required)


def rejection(info: dict[str, Any]) -> str | None:
    duration = info.get("duration") or 0
    if not MIN_SECONDS <= duration <= MAX_SECONDS:
        return "duration"
    if (info.get("view_count") or 0) < MIN_VIEWS:
        return "views"
    if info.get("live_status") not in (None, "not_live", "was_live"):
        return "live"
    if len(info.get("heatmap") or []) < 50:
        return "no_heatmap"
    return None


class Transcriber:
    """YouTube's own ASR track first; local Whisper when YouTube blocks captions."""

    def __init__(self, args: argparse.Namespace, workdir: Path) -> None:
        from youtube_transcript_api import YouTubeTranscriptApi

        self.api = YouTubeTranscriptApi()
        self.args = args
        self.workdir = workdir
        self.whisper: Any = None
        self.api_blocked_until = 0.0

    def transcript(self, video_id: str, language: str) -> dict[str, Any] | None:
        if not self.args.whisper_only and time.time() >= self.api_blocked_until:
            result = self._from_youtube(video_id, language)
            if result is not None:
                return result
        if self.args.no_whisper:
            return None
        return self._from_whisper(video_id)

    def _from_youtube(self, video_id: str, language: str) -> dict[str, Any] | None:
        preferred = [language, *(code for code in ("en", "hi") if code != language)]
        try:
            listing = self.api.list(video_id)
            try:
                track = listing.find_generated_transcript(preferred)
            except Exception:  # noqa: BLE001 - fall back to a creator-made track
                track = listing.find_transcript(preferred)
            lines = [
                {"text": s.text, "start": s.start, "duration": s.duration}
                for s in track.fetch().snippets
            ]
        except Exception as exc:  # noqa: BLE001
            name = type(exc).__name__
            if name in BLOCKED:
                # Try YouTube again in 30 minutes; Whisper covers the gap.
                self.api_blocked_until = time.time() + 1800
                log.warning("YouTube captions blocked (%s); using Whisper for 30 min", name)
            else:
                log.info("no YouTube captions for %s (%s)", video_id, name)
            return None
        return {
            "generated": track.is_generated,
            "source": "youtube",
            "language": track.language_code,
            "lines": lines,
        }

    def _from_whisper(self, video_id: str) -> dict[str, Any] | None:
        if self.whisper is None:
            self.whisper = self._load_whisper()
        options = {
            **_QUIET,
            "skip_download": False,
            "format": "bestaudio[ext=m4a]/bestaudio",
            "outtmpl": str(self.workdir / "%(id)s.%(ext)s"),
        }
        try:
            with yt_dlp.YoutubeDL(options) as ydl:
                ydl.extract_info(f"https://www.youtube.com/watch?v={video_id}", download=True)
            audio = next(self.workdir.glob(f"{video_id}.*"))
            segments, info = self.whisper.transcribe(
                str(audio),
                vad_filter=True,
                condition_on_previous_text=False,
                beam_size=1,
            )
            lines = [
                {"text": s.text.strip(), "start": s.start, "duration": s.end - s.start}
                for s in segments
                if s.text.strip()
            ]
        except Exception as exc:  # noqa: BLE001
            log.warning("whisper failed for %s: %s", video_id, str(exc)[:160])
            return None
        finally:
            for leftover in self.workdir.glob(f"{video_id}.*"):
                leftover.unlink(missing_ok=True)
        return {"generated": True, "source": "whisper", "language": info.language, "lines": lines}

    def _load_whisper(self) -> Any:
        from faster_whisper import WhisperModel

        device = self.args.device
        if device == "auto":
            try:
                import ctranslate2

                device = "cuda" if ctranslate2.get_cuda_device_count() > 0 else "cpu"
            except Exception:  # noqa: BLE001
                device = "cpu"
        compute = "float16" if device == "cuda" else "int8"
        log.info("loading Whisper %s on %s (%s)", self.args.model, device, compute)
        return WhisperModel(self.args.model, device=device, compute_type=compute)


def zip_output() -> Path:
    """Metadata, transcripts and Gemini signals, with paths relative to `evals/interest/raw`."""
    stamp = datetime.now().strftime("%Y%m%d-%H%M")
    target = HERE / f"interest_data_{stamp}.zip"
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as archive:
        for folder in (META, SUBS, SIGNALS):
            for path in sorted(folder.glob("*.json")):
                archive.write(path, path.relative_to(OUT))
    return target


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", type=int, default=500, help="Stop after this many videos.")
    parser.add_argument("--hours", type=float, default=11.0, help="Stop after this long.")
    parser.add_argument("--per-query", type=int, default=60, help="Search results per query.")
    parser.add_argument("--max-per-channel", type=int, default=3)
    parser.add_argument("--sleep", type=float, default=4.0, help="Seconds between videos.")
    parser.add_argument("--model", default="large-v3-turbo", help="faster-whisper model.")
    parser.add_argument("--device", default="auto", choices=["auto", "cpu", "cuda"])
    parser.add_argument("--whisper-only", action="store_true", help="Skip YouTube captions.")
    parser.add_argument("--no-whisper", action="store_true", help="Never transcribe locally.")
    parser.add_argument("--zip-only", action="store_true", help="Just zip what exists.")
    args = parser.parse_args()

    META.mkdir(parents=True, exist_ok=True)
    SUBS.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        handlers=[
            logging.FileHandler(HERE / "collector.log", encoding="utf-8"),
            logging.StreamHandler(sys.stdout),
        ],
    )
    if args.zip_only:
        log.info("wrote %s", zip_output())
        return
    keep_awake()

    exclude_file = HERE / "exclude_ids.txt"
    exclude = set(exclude_file.read_text().split()) if exclude_file.exists() else set()
    done = {p.name.removesuffix(".lines.json") for p in SUBS.glob("*.lines.json")}
    per_channel: dict[str, int] = {}
    for path in META.glob("*.json"):
        channel = json.loads(path.read_text(encoding="utf-8")).get("channel_id") or ""
        per_channel[channel] = per_channel.get(channel, 0) + 1
    deadline = time.time() + args.hours * 3600
    rejected: dict[str, int] = {}
    log.info("starting: %d videos already complete, %d excluded", len(done), len(exclude))

    workdir = Path(tempfile.mkdtemp(prefix="interest_audio_"))
    transcriber = Transcriber(args, workdir)
    flat = yt_dlp.YoutubeDL({**_QUIET, "extract_flat": True})
    full = yt_dlp.YoutubeDL(_QUIET)
    queries = QUERIES[:]
    random.Random(11).shuffle(queries)
    try:
        for query, language in queries:
            if len(done) >= args.target or time.time() > deadline:
                break
            try:
                listing = flat.extract_info(f"ytsearch{args.per_query}:{query}", download=False)
            except Exception as exc:  # noqa: BLE001
                log.warning("search failed for %r: %s", query, str(exc)[:160])
                continue
            for entry in (listing or {}).get("entries") or []:
                if len(done) >= args.target or time.time() > deadline:
                    break
                video_id = entry.get("id")
                if not video_id or video_id in exclude or video_id in done:
                    continue
                duration = entry.get("duration") or 0
                if duration and not MIN_SECONDS <= duration <= MAX_SECONDS:
                    continue
                channel_id = entry.get("channel_id") or ""
                if channel_id and per_channel.get(channel_id, 0) >= args.max_per_channel:
                    continue
                meta_path = META / f"{video_id}.json"
                if meta_path.exists():
                    meta = json.loads(meta_path.read_text(encoding="utf-8"))
                else:
                    try:
                        info = full.extract_info(
                            f"https://www.youtube.com/watch?v={video_id}", download=False
                        )
                    except Exception as exc:  # noqa: BLE001
                        log.info("skip %s: %s", video_id, str(exc)[:120])
                        time.sleep(args.sleep)
                        continue
                    reason = rejection(info)
                    channel_id = info.get("channel_id") or channel_id
                    if reason is None and per_channel.get(channel_id, 0) >= args.max_per_channel:
                        reason = "channel_cap"
                    if reason is not None:
                        rejected[reason] = rejected.get(reason, 0) + 1
                        time.sleep(args.sleep / 2)
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
                        "caption_track": language,
                        "query": query,
                        "heatmap": info.get("heatmap"),
                        "chapters": info.get("chapters"),
                    }
                    meta_path.write_text(json.dumps(meta), encoding="utf-8")
                    per_channel[channel_id] = per_channel.get(channel_id, 0) + 1

                started = time.time()
                transcript = transcriber.transcript(video_id, meta.get("language") or language)
                if transcript is None or len(transcript["lines"]) < 10:
                    rejected["no_transcript"] = rejected.get("no_transcript", 0) + 1
                    time.sleep(args.sleep)
                    continue
                (SUBS / f"{video_id}.lines.json").write_text(
                    json.dumps(transcript), encoding="utf-8"
                )
                if transcript["language"] and transcript["language"] != meta.get("language"):
                    meta["language"] = transcript["language"]
                    meta["caption_track"] = transcript["language"]
                    meta_path.write_text(json.dumps(meta), encoding="utf-8")
                done.add(video_id)
                log.info(
                    "[%d] %s %s via %s in %.0fs  %r",
                    len(done),
                    video_id,
                    transcript["language"],
                    transcript["source"],
                    time.time() - started,
                    (meta.get("title") or "")[:60],
                )
                time.sleep(args.sleep + random.uniform(0, args.sleep))
    except KeyboardInterrupt:
        log.info("interrupted; zipping what was collected")
    finally:
        shutil.rmtree(workdir, ignore_errors=True)
    log.info("finished: %d complete videos; rejected %s", len(done), rejected)


if __name__ == "__main__":
    main()
