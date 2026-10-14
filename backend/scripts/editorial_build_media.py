"""Build the constructed editorial-eval videos, transcripts and gold labels from scripts.

Each `evals/editorial/scripts/<id>.json` is a spoken script whose planted flaws are tagged on
the lines that carry them. This renders every line with macOS `say`, places the audio on a
timeline with exact pauses, burns a plain caption video with FFmpeg, and writes three things:

- `evals/editorial/media/<id>.mp4`: the video the arms review (committed, hash pinned).
- `evals/editorial/transcripts/<id>.json`: segments from the production segmenter.
- `evals/editorial/labels/<id>.json`: the gold labels. Categories, descriptions and expected
  dimensions are authored in the script; only the millisecond spans are measured here.

No network and no model calls. The labels must be committed before any model run.

    cd backend && uv run python scripts/editorial_build_media.py [--only boiled-egg-control]
"""

import argparse
import hashlib
import json
import subprocess
import sys
import tempfile
import wave
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.transcript_service import build_segments

ROOT = Path(__file__).resolve().parents[2]
EDITORIAL = ROOT / "evals" / "editorial"

SAMPLE_RATE = 24_000
LEAD_IN_MS = 600
TAIL_MS = 800
SCHEMA_VERSION = 1


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(command: list[str]) -> None:
    completed = subprocess.run(command, capture_output=True, check=False)
    if completed.returncode != 0:
        tail = completed.stderr.decode("utf-8", "replace").strip().splitlines()[-3:]
        raise RuntimeError(f"{command[0]} failed: {' | '.join(tail)}")


def synthesize(text: str, *, voice: str, rate: int, workdir: Path, name: str) -> bytes:
    """One spoken line as 16-bit mono PCM at SAMPLE_RATE."""
    aiff = workdir / f"{name}.aiff"
    wav = workdir / f"{name}.wav"
    run(["say", "-v", voice, "-r", str(rate), "-o", str(aiff), "--", text])
    run(["ffmpeg", "-y", "-i", str(aiff), "-ar", str(SAMPLE_RATE), "-ac", "1", str(wav)])
    with wave.open(str(wav), "rb") as handle:
        return handle.readframes(handle.getnframes())


def silence(milliseconds: int) -> bytes:
    return b"\x00\x00" * (SAMPLE_RATE * milliseconds // 1000)


def pcm_ms(pcm: bytes) -> int:
    return len(pcm) // 2 * 1000 // SAMPLE_RATE


def srt_time(milliseconds: int) -> str:
    hours, rest = divmod(milliseconds, 3_600_000)
    minutes, rest = divmod(rest, 60_000)
    seconds, millis = divmod(rest, 1000)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d},{millis:03d}"


def wrap(text: str, width: int = 46) -> str:
    lines: list[str] = []
    current = ""
    for word in text.split():
        if current and len(current) + 1 + len(word) > width:
            lines.append(current)
            current = word
        else:
            current = f"{current} {word}".strip()
    if current:
        lines.append(current)
    return "\n".join(lines)


def render_video(
    *, wav: Path, srt: Path, title: str, duration_ms: int, output: Path, workdir: Path
) -> None:
    """A plain title card with burned captions: audio-led, deliberately low bitrate."""
    title_file = workdir / "title.txt"
    title_file.write_text(title)
    style = "FontSize=18,PrimaryColour=&H00FFFFFF&,Alignment=2,MarginV=40,Outline=1"
    video_filter = (
        f"drawtext=textfile={title_file}:fontcolor=white:fontsize=26:x=(w-text_w)/2:y=40,"
        f"subtitles={srt}:force_style='{style}'"
    )
    run(
        [
            "ffmpeg",
            "-y",
            "-f",
            "lavfi",
            "-i",
            f"color=c=0x14213d:s=640x360:r=5:d={duration_ms / 1000:.3f}",
            "-i",
            str(wav),
            "-vf",
            video_filter,
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-crf",
            "34",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            "-b:a",
            "40k",
            "-shortest",
            "-movflags",
            "+faststart",
            str(output),
        ]
    )


def spread_words(text: str, start_ms: int, end_ms: int) -> list[dict[str, Any]]:
    """Word timings proportional to length, so the production segmenter can run unchanged."""
    words = text.split()
    total = sum(len(word) + 1 for word in words)
    cursor = start_ms
    result: list[dict[str, Any]] = []
    for word in words:
        span = round((end_ms - start_ms) * (len(word) + 1) / total)
        result.append({"word": word, "startMs": cursor, "endMs": min(end_ms, cursor + span)})
        cursor += span
    if result:
        result[-1]["endMs"] = end_ms
    return result


def contiguous_groups(positions: list[int]) -> list[list[int]]:
    groups: list[list[int]] = []
    for position in positions:
        if groups and position == groups[-1][-1] + 1:
            groups[-1].append(position)
        else:
            groups.append([position])
    return groups


def build_one(script_path: Path, *, out_dir: Path) -> None:
    script = json.loads(script_path.read_text())
    video_id: str = script["id"]
    lines: list[dict[str, Any]] = script["lines"]
    spans: list[tuple[int, int]] = []
    words: list[dict[str, Any]] = []

    with tempfile.TemporaryDirectory() as temp:
        workdir = Path(temp)
        timeline = silence(LEAD_IN_MS)
        for index, line in enumerate(lines):
            pcm = synthesize(
                line["text"],
                voice=line.get("voice", script["voice"]),
                rate=int(line.get("rate", script["rate"])),
                workdir=workdir,
                name=f"line{index:03d}",
            )
            start_ms = pcm_ms(timeline)
            timeline += pcm
            end_ms = pcm_ms(timeline)
            spans.append((start_ms, end_ms))
            words.extend(spread_words(line["text"], start_ms, end_ms))
            timeline += silence(int(line.get("pauseMs", 400)))
        timeline += silence(TAIL_MS)
        duration_ms = pcm_ms(timeline)

        wav = workdir / "full.wav"
        with wave.open(str(wav), "wb") as handle:
            handle.setnchannels(1)
            handle.setsampwidth(2)
            handle.setframerate(SAMPLE_RATE)
            handle.writeframes(timeline)
        srt = workdir / "captions.srt"
        srt.write_text(
            "\n".join(
                f"{n}\n{srt_time(start)} --> {srt_time(end)}\n{wrap(line['text'])}\n"
                for n, (line, (start, end)) in enumerate(zip(lines, spans, strict=True), 1)
            )
        )
        media_path = out_dir / "media" / f"{video_id}.mp4"
        media_path.parent.mkdir(parents=True, exist_ok=True)
        render_video(
            wav=wav,
            srt=srt,
            title=script["title"],
            duration_ms=duration_ms,
            output=media_path,
            workdir=workdir,
        )

    segments = build_segments(words)
    transcript_path = out_dir / "transcripts" / f"{video_id}.json"
    transcript_path.parent.mkdir(parents=True, exist_ok=True)
    transcript_path.write_text(
        json.dumps(
            {
                "videoId": video_id,
                "language": script["language"],
                "durationMs": duration_ms,
                "segments": [
                    {key: segment[key] for key in ("segmentId", "startMs", "endMs", "text")}
                    for segment in segments
                ],
            },
            indent=2,
        )
        + "\n"
    )

    issues = []
    for issue in script["issues"]:
        primary = [i for i, line in enumerate(lines) if issue["id"] in line.get("issues", [])]
        extra = [
            i for i, line in enumerate(lines) if issue["id"] in line.get("alsoAcceptIssues", [])
        ]
        if not primary:
            raise ValueError(f"{video_id}: issue {issue['id']} is not tagged on any line")
        issues.append(
            {
                "id": issue["id"],
                "category": issue["category"],
                "startMs": spans[primary[0]][0],
                "endMs": spans[primary[-1]][1],
                "additionalSpans": [
                    {"startMs": spans[group[0]][0], "endMs": spans[group[-1]][1]}
                    for group in contiguous_groups(extra)
                ],
                "description": issue["description"],
                "expectedDimension": issue["expectedDimension"],
            }
        )
    tagged = {tag for line in lines for tag in line.get("issues", [])}
    if tagged != {issue["id"] for issue in script["issues"]}:
        raise ValueError(f"{video_id}: line tags and declared issues disagree")

    label = {
        "schemaVersion": SCHEMA_VERSION,
        "videoId": video_id,
        "title": script["title"],
        "platform": script["platform"],
        "language": script["language"],
        "audience": script["audience"],
        "brief": script["brief"],
        "clean": not issues,
        "durationMs": duration_ms,
        "source": {
            "kind": "constructed",
            "script": f"scripts/{video_id}.json",
            "scriptSha256": sha256(script_path),
            "media": f"media/{video_id}.mp4",
            "mediaSha256": sha256(media_path),
            "tts": f"macOS say, voice {script['voice']}, {script['rate']} wpm",
        },
        "issues": issues,
    }
    label_path = out_dir / "labels" / f"{video_id}.json"
    label_path.parent.mkdir(parents=True, exist_ok=True)
    label_path.write_text(json.dumps(label, indent=2) + "\n")
    print(f"{video_id}: {duration_ms / 1000:.1f}s, {len(segments)} segments, {len(issues)} issues")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--only", help="Build one script id.")
    parser.add_argument("--out", type=Path, default=EDITORIAL)
    args = parser.parse_args()
    scripts = sorted((EDITORIAL / "scripts").glob("*.json"))
    if args.only:
        scripts = [path for path in scripts if path.stem == args.only]
    if not scripts:
        raise SystemExit("no scripts matched")
    for script_path in scripts:
        build_one(script_path, out_dir=args.out)


if __name__ == "__main__":
    main()
