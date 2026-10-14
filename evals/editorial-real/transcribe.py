"""Local-only ASR for the downloaded CC BY videos; no review or cloud calls.

From backend/: uv run --with mlx-whisper python ../evals/editorial-real/transcribe.py ID ...
Existing transcripts are skipped. Remove one explicitly before regenerating it.
"""

import argparse
import hashlib
import json
import subprocess
from importlib.metadata import version
from pathlib import Path

import mlx_whisper
from huggingface_hub import snapshot_download

SET = Path(__file__).resolve().parent
MEDIA = SET.parents[1] / "fixtures" / "media" / "editorial-real"
MODEL = "mlx-community/whisper-large-v3-turbo"
MODEL_REVISION = "a4aaeec0636e6fef84abdcbe3544cb2bf7e9f6fb"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("video_ids", nargs="+")
    args = parser.parse_args()
    (SET / "transcripts").mkdir(parents=True, exist_ok=True)
    for video_id in args.video_ids:
        media = MEDIA / f"{video_id}.mp4"
        target = SET / "transcripts" / f"{video_id}.json"
        if target.exists():
            print(f"skip existing {target.name}", flush=True)
            continue
        probe = subprocess.check_output(
            [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "json",
                str(media),
            ],
            text=True,
        )
        duration_ms = round(float(json.loads(probe)["format"]["duration"]) * 1000)
        print(f"transcribing {video_id} locally", flush=True)
        result = mlx_whisper.transcribe(
            str(media),
            path_or_hf_repo=snapshot_download(MODEL, revision=MODEL_REVISION),
            condition_on_previous_text=False,
            word_timestamps=True,
            language="en",
        )
        raw = MEDIA / f"{video_id}.asr.json"
        raw.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
        segments = [
            {
                "segmentId": f"seg-{index + 1}",
                "startMs": max(0, min(duration_ms, round(float(segment["start"]) * 1000))),
                "endMs": max(0, min(duration_ms, round(float(segment["end"]) * 1000))),
                "text": str(segment["text"]).strip(),
            }
            for index, segment in enumerate(result["segments"])
            if str(segment["text"]).strip()
        ]
        payload = {
            "videoId": video_id,
            "language": result["language"],
            "durationMs": duration_ms,
            "source": {
                "kind": "local_asr",
                "model": MODEL,
                "modelRevision": MODEL_REVISION,
                "mlxWhisperVersion": version("mlx-whisper"),
                "conditionOnPreviousText": False,
                "wordTimestamps": True,
                "mediaSha256": hashlib.sha256(media.read_bytes()).hexdigest(),
            },
            "segments": segments,
        }
        target.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n")
        print(f"wrote {target.name}: {len(segments)} segments", flush=True)


if __name__ == "__main__":
    main()
