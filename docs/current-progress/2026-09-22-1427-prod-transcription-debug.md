# Progress — 2026-09-22 14:27 UTC — prod transcription debugged end to end

User reported uploads stuck after the push. Cloud Run logs showed every `GET /jobs/{jobId}`
poll 500ing. Four issues found and fixed; the pipeline is now verified working against the
real project. Uncommitted (not requested).

## 1. Missing Firestore index (the 500s)

`GET /jobs/{jobId}` runs a collection-group query on `jobs.jobId`, which needs a
single-field collection-group exemption — a composite index is rejected by the API as "not
necessary" (learned the hard way via a failed apply). Added
`google_firestore_field.jobs_job_id` (collection ASC+DESC preserved, collection-group ASC
added) in `infra/firestore_indexes.tf`; applied, state clean, API confirms all three READY.
All other app queries audited — no other composite/index needs.

## 2. Background worker never ran on Cloud Run

The stuck job was still `queued` (never even reached `mark_running`): with default CPU
throttling the container freezes after the 202 response, so the background STT task never
executes. Set `--no-cpu-throttling` live via `gcloud run services update` (new revision
serving) and added the flag to `.github/workflows/deploy.yml` so it sticks.

## 3. Wrong STT model (two rounds)

- `chirp_3` (our default + design docs): `400 ... does not exist in us-central1`.
- `chirp_2`: `403 ... no longer generally available` for this project/locale.
- Per current Google docs (Chirp 3 model page, 2026-09-18), `chirp_3` exists but is not in
  `us-central1` yet. Switched default to **`latest_long`** (evergreen, standard pricing,
  official-sample-backed). Updated `config.py`, both `.env` files (prod `.env` via script,
  never read), `stt.py` + worker docstrings, `backend-plan.md`, `workstreams.md`, AGENTS.md
  gotcha. If `latest_long` ever 403s, the immediate fallback is `long`.

## 4. Batch requires an output config

`400 Recognition output configuration must be specified.` Fixed with
`RecognitionOutputConfig(inline_response_config=InlineOutputConfig())` — word timings come
back in the operation response (right size for demo-scale videos; hour-long files would use
a GCS prefix instead). Parser updated to the real shape
(`results[].inline_result.alternatives[].words[]`); unit tests updated + a skips-GCS-results
case added.

## Verified live

Ran `run_transcribe` for the stuck job from the backend venv with ADC: **TRANSCRIPT_ID
`0c627d38…`, job `succeeded`, project `ready`**, canonical JSON + VTT in GCS, transcript doc
+ segments in Firestore. Suite: 125 passed, ruff + mypy clean.

## The twist: 0 words is correct

The test video (`.../source/250c…mp4`, 20s, AAC stereo) measures **-91 dB mean/max volume —
digital silence**. STT correctly returns nothing. To see a real transcript, re-upload a video
with speech (e.g. anything in `fixtures/media/`).

## Small UX addition

Silent audio now succeeds with job message "Completed — no speech detected" instead of a
bare "Completed" (`mark_succeeded` takes an optional message; worker test added), so the
processing card explains the empty transcript.

## To finish

- Commit + push this batch (TF index, deploy CPU flag, model + inline-config fixes, empty
  hint, this note) — prod still runs the old code until then.
- After push: re-upload a speaking video to watch the whole loop live.
