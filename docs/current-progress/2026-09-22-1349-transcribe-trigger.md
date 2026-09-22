# Progress — 2026-09-22 13:49 UTC — real transcription trigger

`complete_upload` now actually runs transcription: it queues the job for the response and
schedules the existing `run_transcribe` worker via FastAPI background tasks. Uploads
end to end (upload → STT → transcript → project ready) with zero new infra. Uncommitted
(not requested).

## What changed (`backend/` only; no frontend changes needed)

- **`workers/transcribe_worker.py`**: new `transcribe_after_response()` builds live
  dependencies (Firestore, Storage, services, STT provider, settings) and adds
  `run_transcribe` to the response's `BackgroundTasks`. Documented as the interim trigger
  until the Pub/Sub path lands.
- **`dependencies.py`**: new `TranscribeScheduler` callable + `get_transcribe_scheduler()`
  (default: `transcribe_after_response`). Injectable like `get_identity_deleter` so tests
  record scheduling instead of running the worker.
- **`api/uploads.py`**: `complete_upload` takes `BackgroundTasks` + scheduler and schedules
  a run unless the job is already `succeeded`/`running`. Consequences:
  - First complete (queued) → runs. Failed job + re-complete → retries.
  - Finished job + re-complete → no new run (still returns the same job id).
  - Known narrow race: two simultaneous completes while still `queued` schedule twice;
    the worker is idempotent at terminal states but concurrent runs last-win. Acceptable
    for the demo; Pub/Sub delivery has the same shape.
- **Tests (`test_uploads_api.py`)**: fixture overrides the scheduler with a recorder;
  flow test asserts the schedule call; new tests cover skip-when-succeeded and
  retry-when-failed.

## Verification

- `pytest` 123 passed (was 121), `ruff check` clean, `mypy` clean.

## Ops notes / next steps

- Needs real GCP at runtime: STT API enabled, `GEMINI_API_KEY` not required for this path
  (STT uses ADC/service account), bucket + Firestore per `infra/`.
- **Cloud Run CPU caveat:** the default service throttles CPU after the response returns,
  which can stall the background STT poll on a quiet instance. If deployed demos stick at
  "Transcribing…", set CPU-always-allocated (`gcloud run deploy … --no-cpu-throttling`) or
  keep a warm instance during the demo. Local `uvicorn` is unaffected.
- Jobs queued before this change are stuck `queued` but recoverable: re-POST `complete`
  schedules them (idempotent per asset).
- Production follow-up (unchanged plan): Storage `object finalized` → Pub/Sub → push
  endpoint → `run_transcribe`; `build_worker_services` already bundles the deps for it.
- After this: **analysis + heatmap** (flagship), real caption `<track>` from the stored VTT.
