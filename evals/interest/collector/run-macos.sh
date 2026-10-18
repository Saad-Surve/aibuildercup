#!/usr/bin/env bash
# Overnight data run for the Resonance interest model, on macOS.
#
#   ./run-macos.sh test      - 2-video smoke test (~5-10 min). Run this first.
#   ./run-macos.sh           - full run: collect up to 7h, then Gemini signals, then zip.
#   ./run-macos.sh signals   - only the Gemini signal pass + zip (collection already done).
#   ./run-macos.sh zip-only  - just re-pack the zip from what exists.
#   ./run-macos.sh status    - show collection counts, no network, no cost.
#
# Resumable: stop any time (Ctrl+C) and run again; finished videos are skipped.
# Keeps the Mac awake during the long phases with `caffeinate -i`.
# Result to send back: interest_data_<date>.zip (paths relative to evals/interest/raw).
#
# Tunables via environment, e.g. TARGET=300 HOURS=5 ./run-macos.sh
#   TARGET=500  HOURS=7  MODEL=small  SIGNALS_FIRST=1500  SIGNALS_RETRY=500  CONCURRENCY=2
set -euo pipefail
cd "$(dirname "$0")"
export PYTHONUTF8=1
export PYTHONIOENCODING=utf-8

REPO="$(cd ../../.. && pwd)"
TARGET="${TARGET:-500}"
HOURS="${HOURS:-7}"
MODEL="${MODEL:-small}"
SIGNALS_FIRST="${SIGNALS_FIRST:-1500}"
SIGNALS_RETRY="${SIGNALS_RETRY:-500}"
CONCURRENCY="${CONCURRENCY:-2}"

if [[ "$(uname)" != "Darwin" ]]; then
  echo "This script is for macOS. On Windows use run.bat; elsewhere run: uv run collect.py --help" >&2
  exit 1
fi

if ! command -v uv >/dev/null 2>&1; then
  echo "Installing uv..."
  curl -LsSf https://astral.sh/uv/install.sh | sh
  export PATH="$HOME/.local/bin:$PATH"
fi
if ! command -v uv >/dev/null 2>&1; then
  echo "uv is not on PATH. Open a new terminal and run this again." >&2
  exit 1
fi
if ! command -v gcloud >/dev/null 2>&1; then
  echo "Install the Google Cloud CLI first: https://cloud.google.com/sdk/docs/install" >&2
  exit 1
fi
if ! gcloud auth application-default print-access-token >/dev/null 2>&1; then
  echo "Not signed in for Gemini. Run these two commands, then run this script again:" >&2
  echo "  gcloud auth application-default login" >&2
  echo "  gcloud auth application-default set-quota-project habeas-codus" >&2
  exit 1
fi
if ! command -v ffmpeg >/dev/null 2>&1; then
  echo "WARNING: ffmpeg not found. Install with: brew install ffmpeg" >&2
fi

status() {
  echo "meta:    $(ls ../raw/meta/*.json 2>/dev/null | wc -l | tr -d ' ') videos found"
  echo "subs:    $(ls ../raw/subs/*.lines.json 2>/dev/null | wc -l | tr -d ' ') transcripts ready"
  echo "signals: $(ls ../raw/signals/*.json 2>/dev/null | wc -l | tr -d ' ') Gemini-rated videos"
}

collect() { # $1=target $2=hours $3=model
  echo "=== 1/3 Collecting videos and transcripts (up to $2h, target $1) ==="
  echo "Progress logs to collector.log; stop any time with Ctrl+C and re-run to resume."
  caffeinate -i uv run collect.py --target "$1" --hours "$2" --model "$3"
}

signals() { # $1=first-pass cap $2=retry cap
  echo "=== 2/3 Gemini signals (bounded to $1+$2 calls, ~\$6 max) ==="
  cd "$REPO/backend"
  # Low concurrency on purpose: higher values hit Gemini 429s.
  caffeinate -i uv run --with pyarrow python scripts/interest_train.py signals \
    --max-calls "$1" --concurrency "$CONCURRENCY" --cbc-train 0 --cbc-test 0
  # Second pass retries videos that hit rate limits the first time.
  caffeinate -i uv run --with pyarrow python scripts/interest_train.py signals \
    --max-calls "$2" --concurrency 2 --cbc-train 0 --cbc-test 0
  cd - >/dev/null
}

pack() {
  echo "=== 3/3 Packing results ==="
  uv run collect.py --zip-only
  echo
  echo "Done. Send back the interest_data_*.zip file in:"
  echo "  $(pwd)"
  status
}

case "${1:-full}" in
  test)
    echo "=== Smoke test: 2 videos, then Gemini signals ==="
    collect 2 0.5 "$MODEL"
    cd "$REPO/backend"
    uv run --with pyarrow python scripts/interest_train.py signals \
      --max-calls 10 --concurrency 2 --cbc-train 0 --cbc-test 0
    cd - >/dev/null
    echo
    echo 'If you see "done": 2 (or 1) above with no errors, start the real run with: ./run-macos.sh'
    ;;
  signals)
    signals "$SIGNALS_FIRST" "$SIGNALS_RETRY"
    pack
    ;;
  zip-only)
    pack
    ;;
  status)
    status
    ;;
  full|"")
    collect "$TARGET" "$HOURS" "$MODEL"
    signals "$SIGNALS_FIRST" "$SIGNALS_RETRY"
    pack
    ;;
  *)
    echo "Usage: $0 [test|signals|zip-only|status]  (no argument = full run)" >&2
    exit 1
    ;;
esac
