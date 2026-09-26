# Progress — 2026-09-26 10:07 UTC — speaker diarization

## What I did

Enabled speaker diarization on the STT path and carried speakers end to end.

- **Question that started it:** diarization was *not* enabled (only word time offsets +
  punctuation were requested) and `normalize_words` dropped any speaker label.
- **Provider** (`backend/app/providers/stt.py`): `transcribe(...)`/`_real(...)` gain
  `enable_diarization`; when set, `RecognitionFeatures.diarization_config =
  SpeakerDiarizationConfig()`. Word extraction now reads `WordInfo.speaker_label` and emits
  `speaker` (0/absent → `None`).
- **Config** (`backend/app/config.py`): new `stt_enable_diarization: bool = True`
  (`STT_ENABLE_DIARIZATION=true` in `.env.example`).
- **Worker** (`transcribe_worker.py`): both STT call sites (primary + normalized-audio retry)
  pass the flag.
- **Transcript service** (`transcript_service.py`):
  - `normalize_words` carries `speaker`.
  - `build_segments` splits on speaker change, so every cue is one voice; segments carry
    `speaker`.
  - Persisted transcript doc gets `speakerCount`; segment docs get `speaker`; the canonical GCS
    JSON segments get `speaker`.
  - `build_vtt` emits `<v Speaker N>` and `build_srt` prefixes `Speaker N:` — **only when more
    than one speaker** is present (single-speaker output is unchanged).
  - `get_segment` and `_to_transcript` surface `speaker`.
- **Contracts/schema:** `TranscriptSegment.speaker: int|null` in `contracts/openapi.yaml` and
  `backend/app/schemas/transcripts.py`; `docs/technical-design/db-design.md` segment example and
  `api-design.md` regenerate example (default flipped to `true`).
- **Web:** `TranscriptSegment.speaker?: number | null` in `lib/types.ts`; transcript panel shows
  a `S1`/`S2` chip per cue and a "N speakers" count in the header when 2+ speakers are detected.

## Decisions / gotchas

- **Graceful degradation.** `_real` retries once **without** diarization if the first call fails
  with an error mentioning "diarization" (and only then). This protects the demo if a
  model/region combination rejects the feature, without doubling calls on genuine failures.
- **Chirp 3 diarization support could not be verified from the sandbox** (no live docs / no paid
  call). The feature is requested and the fallback covers rejection — **the next live
  transcription is the real test.** If labels come back empty, flip `STT_ENABLE_DIARIZATION=false`.
- STT V2's `SpeakerDiarizationConfig.min/max_speaker_count` are documented as *not currently
  used* — we send an empty config and let the service decide the count.
- Speakers are per-word `int32` labels starting at 1; proto3 omits 0, so 0 is treated as
  "undiarized" (`None`).
- **Existing transcripts** have no `speaker`; the UI degrades cleanly (no chips). A
  re-transcribe/regenerate is required to populate labels.

## Verified

- Backend: `ruff check .` clean, `mypy app` clean (68 files).
- Functional smoke of `normalize_words`/`build_segments`/`build_vtt`/`build_srt` with a fake
  two-speaker response: correct per-speaker segment splits and voice tags; single/no-speaker
  output stays unbranded.
- `contracts/openapi.yaml` parses; `TranscriptSegment.speaker` is `['integer','null']`.
- Web: `bun run lint` (oxlint), `bunx tsc --noEmit`, `bun run build`, `bun run lint:eslint` all
  clean (one pre-existing `no-img-element` warning in `project-card.tsx`).

## Not done / next step

- **Run a real transcription** on a two-speaker fixture in `fixtures/media/` and confirm
  `speakerLabel` actually comes back from `chirp_3` in `us`. If not, either disable the flag or
  investigate a different model/region.
- Optional: feed speakers into analysis prompts / heatmap (not needed for the demo).
