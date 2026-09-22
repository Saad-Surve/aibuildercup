# Progress — 2026-09-22 16:22 UTC — STT v2: real transcripts (timestamps + multilingual)

The transcription pipeline was silently producing **zero words for every video**. Root causes
found and fixed; verified live against `fixtures/media/` in both English and Hindi. Uncommitted
(not requested).

## Why it was broken (three separate bugs)

1. **Parser read the wrong field.** `_response_to_dict` did
   `inline.alternatives`, but the real inline shape is
   `inline_result.transcript.results[].alternatives[].words[]`. Because it used
   `getattr(..., [])`, it returned `[]` unconditionally — every transcript was empty, and the
   job still "succeeded".
2. **Per-file errors were discarded.** Batch recognition reports failures in-band at
   `file_result.error` (a `google.rpc.Status`), not as an operation exception. The provider
   ignored it, so a failed file looked like a silent video.
3. **AAC-in-video decoding.** `auto_decoding_config` rejects MP4/MOV/M4A AAC with
   `400 Audio data does not appear to be in a supported encoding`. All `fixtures/media/`
   videos are MP4/AAC 44.1 kHz stereo, so auto-detect failed on every upload.

## The fix (`backend/` only; no contract or frontend change)

- **`providers/stt.py`**: parser now walks `inline_result.transcript.results[].alternatives[].words[]`
  and returns `{"words": [...], "language": <detected>}`. Per-file `error` is raised as a
  `RuntimeError` so the job fails loudly instead of "succeeding" empty. Container-aware decoding:
  `.mp4/.m4v -> MP4_AAC`, `.mov -> MOV_AAC`, `.m4a -> M4A_AAC` (explicit config with sample rate
  + channels, since the API rejects 0); everything else stays on auto-detect.
- **Multilingual**: switched to **`chirp_3`** on the **`us` multi-region** with
  `language_codes=["auto"]` (language-agnostic transcription). `chirp_3` is GA on `us`, **not**
  in `us-central1` — this is what the previous session hit and worked around with `long`. The
  detected language is persisted on the transcript; project `primaryLanguage` is the fallback.
- **`config.py`**: `model_stt=chirp_3`, new `stt_region="us"`, `stt_sample_rate_hz=44100`,
  `stt_audio_channel_count=2`.
- **`workers/transcribe_worker.py`**: passes `["auto"]`, stores `response["language"]` (fallback
  `_bcp47(project.primaryLanguage)`). Fixed the old bare-code bug where any language without a
  region became `"<code>-US"` (e.g. `hi` -> `hi-US`); now mapped via `_LANGUAGE_TAGS`.
- **Provider interface** (`base.py`): `transcribe(language_codes: list[str])` replaces
  `language: str`.
- **Docs**: purged stale Chirp wording; documented the `us`-multi-region STT exception in
  AGENTS, README, `backend-plan.md`, `infra-plan.md`.

## Verified live (real API, ADC, project habeas-codus)

- `career_advice.mp4` -> detected `en`, **677 words**, word timings (first 8.0s, last 240s).
- `hindi_education.mp4` -> detected `hi`, **455 words**, Devanagari text + timings.

Suite: **131 passed**, ruff + mypy clean. Temp GCS objects and debug scripts removed.

## Gotchas / notes

- Explicit AAC decoding needs non-zero `sample_rate_hertz` + `audio_channel_count`; the API
  tolerates approximate values but accuracy shifts, so defaults are 44.1 kHz stereo. A video
  that isn't AAC/MP4 falls back to auto-detect and now surfaces a clear error if unsupported.
- `language_codes=["auto"]` requires a Chirp model; don't pair it with `long`.
- `chirp_3` is ~$0.016/min (not the free `long` tier). Demo-scale only; still cheap vs the kill
  switch.

## To finish

- Commit + push (prod Cloud Run picks up `config.py` defaults automatically; no deploy-workflow
  env change needed). After push: upload a speaking video and confirm the full loop.
