# Overnight data run (Windows)

This collects public YouTube videos' "Most Replayed" graphs plus timed transcripts, rates every
five seconds with Gemini, and zips the result. That zip is the training data for the
audience-interest model (`evals/interest/README.md`). It runs unattended: about 7 hours of
collection, then up to an hour of Gemini.

## One-time setup (about 10 minutes)

1. **Get the repo** on the Windows machine (`git clone` or a copy), then open a terminal in
   `evals\interest\collector`.
2. **Install the Google Cloud CLI**: <https://cloud.google.com/sdk/docs/install>
3. **Sign in for Gemini** (your account needs Vertex AI User on `habeas-codus`):
   ```bat
   gcloud auth application-default login
   gcloud auth application-default set-quota-project habeas-codus
   ```
4. **Smoke test** (about 5 minutes; installs `uv` and Python packages on first run):
   ```bat
   run.bat test
   ```
   It should end with `"done": 2` (or 1) and `"failed": 0` from the Gemini step.

## The overnight run

```bat
run.bat
```

- Keep the laptop **plugged in**. The script stops Windows from sleeping while it runs. If
  the lid-close action is set to "Sleep", leave the lid open.
- It stops by itself after 500 videos or 7 hours, runs the Gemini pass (capped at 2,000
  calls, about $6 at most), and prints where the zip is. On a CPU-only laptop, Whisper uses
  the `small` model.
- **Send back** `evals\interest\collector\interest_data_<date>.zip`.

If it stops early (crash, reboot, Ctrl+C), run `run.bat` again: finished videos are skipped.
If collection already finished and only Gemini is left, run `run.bat signals`.

## What it does, and what it keeps

- Searches about 40 talking-head and explainer topics in English and Hindi, and keeps
  4–25 minute videos with at least 100k views and a Most Replayed graph, at most three per
  channel. The 243 videos already collected are skipped (`exclude_ids.txt`).
- Transcripts come from YouTube's own captions when available. If YouTube blocks caption
  requests (it does after a few dozen from one IP), it downloads **audio only**, transcribes
  it locally with Whisper, and deletes the audio straight away.
- It keeps only metadata, the replay graph, the transcript and Gemini's per-moment ratings,
  as small JSON files under `evals\interest\raw\` (a few MB in total).

## Options

`uv run collect.py --help` lists them. The useful ones:

| Option | When |
|---|---|
| `--model large-v3-turbo` | Machine with an NVIDIA GPU: better transcripts (`run.bat` uses `small` for CPU-only laptops) |
| `--device cuda` | Force the NVIDIA GPU for Whisper (`auto` picks it when available) |
| `--hours 6 --target 300` | Shorter run |
| `--whisper-only` | YouTube captions keep failing; transcribe everything locally |

Progress is printed and saved to `collector.log`. Each finished video logs a line like
`[57] abc123 en via youtube in 3s 'Video title'`.

## Using the zip (on the training machine)

```bash
cd evals/interest/raw && unzip -n ~/Downloads/interest_data_*.zip
uv run --project backend --with pyarrow python backend/scripts/interest_train.py train --dry-run
uv run --project backend --with pyarrow python backend/scripts/interest_train.py train
```

`-n` keeps the files that already exist. Check the dry-run numbers against
`evals/interest/results.json` before writing the new model.
