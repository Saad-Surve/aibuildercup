# Progress — 2026-09-22 13:13 UTC — transcription vertical slice

Implements next-step #1 from the 2026-09-21 handoff: the queued `transcribe` job now has a
consumer (STT provider + worker), a transcript read API, and a workspace transcript viewer.
Uncommitted (not requested).

## Backend

- **`app/providers/stt.py` (new).** Cassette-aware STT provider mirroring `llm.py`:
  `on`/`auto` replay by `sha256(stt + model + stt-v1 + canonicalRequest)`; `auto` records on
  miss; `off` never writes. Real path is Speech-to-Text V2 **batch** recognition, model
  `chirp_3`, endpoint `{region}-speech.googleapis.com` (region stays `us-central1`).
  Wired into `Providers` as `providers.stt`. No Google SDK in feature code (rule 2 intact).
- **`app/schemas/transcripts.py` (new).** `Transcript`/`TranscriptSegment` match the existing
  `contracts/openapi.yaml` `GET /projects/{id}/transcript` shapes, so **no contract change**.
- **`app/services/transcript_service.py` (new).** Pure, tested helpers: `normalize_words`
  (sanitise/clamp/sort word timings), `build_segments` (sentence-split, ≤14 words, ≤8s),
  VTT/SRT builders + timestamp formatters. `TranscriptService.save()` writes canonical JSON +
  VTT to GCS (`…/transcripts/v{n}.json`, `…/captions/{lang}.vtt`), transcript + segment docs
  to Firestore, bumps `activeTranscriptId`; `get()` reads the active transcript with
  `ownerUid` checks (segment id reattached from doc id).
- **`app/services/paths.py` + `firestore_service.py`.** Added `transcripts_collection_path`,
  `transcript_path`, `transcript_object_path`, `transcript_vtt_object_path` (re-exported).
- **`app/services/job_service.py`.** New lifecycle helpers for workers: `load_for_worker`,
  `mark_running`, `update_progress`, `mark_succeeded`, `mark_failed`.
- **`app/services/project_service.py`.** New `mark_transcript_ready` (status → `ready`,
  summary `{durationMs, transcriptWordCount}`) and `mark_failed`.
- **`app/workers/transcribe_worker.py` (new).** `run_transcribe(...)`: skips terminal jobs
  (idempotent for retried delivery), marks running → STT → normalise → persist → asset
  `ready` → project `ready` → job `succeeded`; every failure path marks job + project
  `failed` with a code/message. Language resolves from `primaryLanguage` (`en` → `en-US`).
- **`app/api/transcripts.py` (new) + `main.py` + `dependencies.py`.**
  `GET /api/projects/{projectId}/transcript`.
- **Tests (127 passing, was 104):** `test_stt_provider` (replay/miss/record/off/gcs-uri),
  `test_transcript_service` (normalisation, segmentation bounds, VTT/SRT, save/get
  roundtrip, 404s, owner isolation), `test_transcribe_worker` (success, idempotency,
  missing-asset, STT-error, unknown-job), `test_transcripts_api` (200/404/401).

## Web

- `lib/types.ts` + `lib/projects.ts`: `Transcript`/`TranscriptSegment`, `getTranscript()`,
  `formatTimestamp()` (m:ss).
- `mocks/handlers.ts`: mock transcription now progresses across job polls
  (queued → running → succeeded), mints a deterministic 5-segment transcript, and flips the
  project to `ready`; new `GET …/transcript` handler (404 `TRANSCRIPT_NOT_READY` before that).
- `components/projects/transcript-panel.tsx` (new): polls `getTranscript` while processing,
  shows transcribing skeleton → clickable segment list (timestamp + text). Clicking seeks
  the video via a `creator-studio:seek` window event.
- `source-video-player.tsx`: listens for the seek event (scoped by `projectId`).
- `project-workspace.tsx`: renders `TranscriptPanel` under the source video; invalidates
  `project` + `transcript` queries when the job succeeds so the badge flips to ready.

## Verification

- Backend: `pytest` 127 passed, `ruff check` clean, `mypy` clean.
- Web: `oxlint` clean, `eslint` 0 errors (1 pre-existing `<img>` advisory), `oxfmt` applied,
  `bun run build` passes.
- Gotcha: `bun run build` initially failed with `Can't resolve 'framer-motion'` — the
  package was declared but absent from `node_modules` (dehydrated install). `bun install`
  fixed it; unrelated to this change.

## Not done / next step

1. **Real trigger (handoff item #2).** Nothing invokes `run_transcribe` yet — `complete_upload`
   still only queues the job. Needs the designed trigger (Storage `object finalized`
   notification or publish in `/complete` → Pub/Sub → worker entrypoint). `run_transcribe`
   takes all deps as args so either host (Cloud Run push handler or Cloud Run Job) can call it.
2. Then: **analysis + heatmap** (flagship), real caption `<track>` from the stored VTT,
   backend-generated `thumbnail` assets.
3. Consider `backend/scripts/seed.py` writing a transcript through `TranscriptService.save`
   so seeded workspaces exercise the same read path as live ones.
