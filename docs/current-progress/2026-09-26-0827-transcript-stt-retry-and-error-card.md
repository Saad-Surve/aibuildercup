# Progress — 2026-09-26 08:27 UTC — transcript fix deployed + failure card now tells the truth

## Why transcripts were failing in prod

The previous session's STT normalization fallback (pure-Python AAC demux + clean `.m4a`
re-mux) was never committed, so the deployed image (`api:4dfb32d1…`) still contained the old
worker that sent the pathological MP4 straight to STT → `An internal error occurred.` The real
GCS `object finalized` → Pub/Sub path then marked the project failed with the generic
`"Transcription failed. Retry from the workspace."`.

Two more real bugs were found while fixing it:

1. **Retry was a no-op that stranded the project.** `POST /assets/{id}/complete` returns the
   existing job via its idempotency key, and `run_transcribe` skips terminal jobs — so
   re-completing a failed upload did nothing, while `queue_transcription` had already flipped
   the project back to `processing`. It could never recover.
2. **The failure card hid the error.** `ProcessingStatusCard` read `job.progress.message`
   (`"Transcribing audio"`) and, after a reload, `project.progress.message` (the generic
   string). The real reason (`Speech recognition failed: …`) lived only on `job.error`, which
   the card never read.

## What changed (backend)

- `backend/app/services/job_service.py`: new `requeue_failed(...)` — resets a **failed** job to
  `queued` (clears `error`, `startedAt`, `finishedAt`, `attempt`). Non-failed jobs are returned
  untouched.
- `backend/app/services/asset_service.py`: `queue_transcription(..., retry_failed=False)`.
  `complete_upload` passes `retry_failed=True`; the Pub/Sub path stays a pure no-op for an
  existing job. Also stops re-marking a project `processing` when the job is already
  `succeeded`/`running` (this used to strand a re-completed ready project).
- `backend/app/workers/transcribe_worker.py`: on STT failure the worker now
  (a) marks the asset `failed`, (b) persists a concrete reason to the **project** via
  `_failure_message(exc)` so it survives a reload, and (c) keeps the same specific reason on
  the job.
- `backend/app/services/media.py` + `storage_service.py` `download_bytes`/`upload_bytes` +
  `fakes.py`: the STT fallback from the previous session, now actually shipped.
- `.github/workflows/deploy.yml`: `--memory 1Gi` (the fallback loads + re-muxes the source in
  memory; 512 Mi was tight for large uploads).

## What changed (web)

- `processing-status-card.tsx`: when failed, the title is **"Transcription failed"**, the
  description says it can be retried, and the message prefers `job.error.message` → the
  project's persisted message. Adds a **"Retry transcription"** button.
- `project-workspace.tsx`: wires the button to `POST /assets/{id}/complete` (the new backend
  requeue), then re-poll project/job/transcript. `sourceAsset` is now computed before the early
  returns so the hook can use it.
- `transcript-panel.tsx`: accepts a `failureMessage` and shows the real reason instead of the
  generic "did not finish" text; non-404 load errors show the actual error message.

## Verified

- **Backend**: `pytest` **281 passed** (2 new retry tests); `ruff` clean; `mypy` clean. The one
  failure, `test_analysis_service.py::test_list_runs_is_newest_first`, is the pre-existing
  Windows coarse-clock tie documented two notes ago — untouched files.
- **Frontend**: `bun run lint` clean; `bun run build` passes with `.env.local`'s
  `NEXT_PUBLIC_API_BASE_URL` overridden to `https://habeas-codus.web.app`.
- **Live production E2E (deployed revision `creator-studio-api-00039-rw9`, 1 Gi)**:
  uploaded the exact failing 27 MB MP4 to a throwaway `smoketest` project under the real bucket
  prefix. The **real GCS → Pub/Sub** trigger ran the deployed worker:
  `transcribe job 39249b71…: STT failed (An internal error occurred.); trying normalized audio`
  → fallback accepted → project `ready`, **transcript 173 words / 23 segments**, correct lyrics
  ("Take me back to the night we met…"). Smoke project, GCS objects and debug objects deleted.

## Deploy / state

- Backend image was built **from the working tree** via Cloud Build and deployed manually as
  `api:manual-202609261334` (no commit, per rule 7). **This is the risk:** the next CI deploy on
  `main` will overwrite it with committed code unless these files are committed. The fix is
  complete but uncommitted.
- Web was built and released to Firebase Hosting from the working tree (same caveat).
- Temporary `roles/iam.serviceAccountTokenCreator` grant on `creator-studio-transcribe@` used
  for the smoke test has been removed.

## Not done / next step

1. **Commit the transcript fix** (backend `media.py`, worker, job/asset services, storage,
   fakes + tests; web card/workspace/panel/hook; the workflow memory line). Otherwise the next
   push to `main` reverts production to the broken worker.
2. The untracked parallel-session files still fail `tsc` (`web/src/lib/avatar.ts`,
   `web/src/components/avatar/*`, `web/src/components/projects/edit-project-dialog.tsx`). They
   had to be moved aside for the web build; they are still untracked and unreferenced.
3. `backend/tests/test_media.py` and the new retry tests are in the working tree.
