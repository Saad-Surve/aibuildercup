# Progress — 2026-09-26 07:35 UTC — fix: transcripts failing on ripper-muxed MP4s + transcript poll gating

## Root cause (transcripts not generating)

The user's upload (`Lord` project `215ba533…`, yt1s.com MP4, 27 MB) failed in STT with
per-file error code 13 `An internal error occurred`. Reproduced directly against the STT API:
- explicit `MP4_AAC` 44100/stereo (our config) → 13 INTERNAL
- same with `en-US` instead of `auto`, and with 48000 Hz → 13 INTERNAL
- `auto` decoding → 3 INVALID_ARGUMENT (expected for AAC-in-MP4)

Box-level parse of the file: the container is pathological — 4991 micro-chunks with
`stsc` runs alternating 1–2 samples/chunk, `sgpd`/`sbgp` sample groups, and a bogus
`mp4a` sample-entry rate (16 Hz while the esds ASC says 44.1 kHz). STT's batch importer
chokes on the container; the AAC-LC essence itself is fine. Earlier phone-camera MP4s
transcribed OK, so this is file-specific, not a general STT outage.
Proof: demuxed the raw AAC frames (pure-Python box parser), re-muxed into a minimal
clean `.m4a` → STT returned 173 words of correct lyrics ("Take me back to the night…").

## What changed (backend)

- **New `backend/app/services/media.py`**: pure-stdlib `extract_aac_track()` (MP4/MOV/M4A
  demux: moov→soun trak→mp4a+esds→ASC rate/channels→stsz/stsc/stco-or-co64→raw AAC frames,
  AAC-LC only) and `mux_m4a()` (minimal single-track `.m4a`). No FFmpeg dependency.
- **`backend/app/workers/transcribe_worker.py`**: on any STT exception for an MP4-family
  source, one bounded retry via `_retry_with_normalized_audio()` — download source,
  demux, stage clean `.m4a` under `{project_prefix}/transcribe-tmp/{jobId}.m4a`
  (delete-path safe), retry STT, delete the temp object. Non-video files, missing AAC
  tracks, and oversize sources keep the original error unchanged.
- **`backend/app/services/storage_service.py` + `tests/fakes.py`**: `StorageClient`
  gains `download_bytes`/`upload_bytes` (real + fake impls; fake `delete_prefix` now
  also clears blobs).
- **Tests**: new `tests/test_media.py` (7 tests: round trips incl. real ripper file,
  chunk-offset self-consistency, garbage/unsupported-ASC rejection); `StubStt` takes a
  response script; 2 new worker tests (retry succeeds + temp cleaned; garbage bytes keep
  original error, single STT call).

## What changed (frontend)

- `web/src/hooks/use-project-transcript.ts`: new `TRANSCRIPT_POLL_MS = 10_000` (was 3 s)
  and `shouldPoll` option — `refetchInterval` is `false` once data exists **or**
  `shouldPoll` is false. Docstring updated.
- `transcript-panel.tsx`: passes `{ shouldPoll: processing }`; settled-without-transcript
  renders a static "Transcript unavailable" card instead of spinning forever.
- `review-panel.tsx`: new optional `transcriptShouldPoll` prop (default true), passed to
  the shared hook so the second observer can't keep polling alone.
- `project-workspace.tsx`: passes `transcriptShouldPoll={processing}`.

## Verified

- **Live E2E on the user's real upload**: new transcribe job on the existing GCS object →
  first STT attempt failed (13), normalized-audio retry accepted → transcript
  `934b393c…`, project `ready`, **23 segments / 173 words**, correct lyrics
  ("Take me back to the night we met…"). Temp object cleaned (0 leftovers).
- Backend: `pytest` 279 passed; `ruff` clean; `mypy` clean.
- Web: `bun run lint` (oxlint) clean.

## Known / not done

- `tests/test_analysis_service.py::test_list_runs_is_newest_first` fails on this machine:
  **pre-existing, untouched by this change** (analysis files not modified). Cause:
  Windows coarse clock → two `datetime.now(UTC)` collide → newest-first sort ties.
  Passes where the clock has µs resolution.
- `bun run build` type-check fails in **other-session untracked files**
  (`web/src/lib/avatar.ts`, `web/src/components/avatar/*`,
  `web/src/components/projects/edit-project-dialog.tsx`) — none of this session's files
  have errors. Left alone (not mine to delete/fix).
- Backend dev server on :8080 predates this change: restart it (or rely on
  `uvicorn --reload` if that is how it was launched) so UI-triggered transcriptions use
  the fallback. Frontend needs no restart (Next dev picks up edits).
- Cleanup: `debug/lord_*.{m4a,aac,mp4}` test objects left in `habeas-codus-media`
  (bucket root, outside any project prefix). Delete when convenient.
- The failed original job `f90b4791…` stays failed as history; the retry job
  `4ca8e5c7…` succeeded and the project is `ready`.
