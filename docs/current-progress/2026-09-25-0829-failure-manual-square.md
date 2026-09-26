# Progress — 2026-09-25 08:29 UTC — Failure UX, manual transcripts, square panes

Uncommitted (not requested — commit only on ask).

## Dismiss + go manual on failure

- The failed status card has an X dismiss button now. Dismissal persists in
  localStorage keyed by `projectId + project.updatedAt`, and the flag is
  read fresh every render — so dismissing hides it, but any NEW failure
  (new timestamp) reappears. No more stuck banner.
- Empty transcript state has "Write manually" next to "Generate transcript":
  `POST /projects/{id}/transcript` starts a blank hand-written transcript
  (409 if one already exists — then PUT applies), flips the project to
  ready, and drops straight into edit mode where "Add the first line" waits.
- New `CreateTranscriptRequest` schema; `save()` was refactored to share a
  `_store_new` helper with `create_manual` (same docs/storage/project
  writes). Contract in `openapi.yaml`.

## Square transcript pane

- Transcript + timeline cards are `rounded-none` like the preview card.

## The error-message bug (why it stayed generic)

- Root cause: after a reload the workspace has no job id in memory, so
  `jobQuery` never runs and the UI fell back to the project's
  `progress.message` — which the worker hardcoded to "Transcription failed.
  Retry from the workspace." The specific STT reason only lived on the job.
- Fix: the worker now writes the specific reason to the project too
  (`Transcription failed: {exc}`), so the message survives reloads. The card
  still prefers `job.error.message` when the job record is at hand.

## No more endless checking

- Transcript + timeline polling is now gated on `processing`: failed/idle
  projects don't poll every 3s. Retranscribe/generate flips the project to
  processing, which resumes polling automatically.

## Verification

- Backend: `pytest` 174 passed (3 new), `ruff` + `mypy` clean.
- Web: `oxlint`/`oxfmt` clean, `eslint` 0 errors (1 pre-existing `<img>`
  advisory), `bun run build` passes.

## Gotchas

- Manual transcripts get `sourceAssetId: ""` and duration from their lines
  (0 when empty) — the panel's asset-duration fallback covers the clamp.
- `POST /transcript` has no `expectedVersion` guard (same single-editor
  assumption as PUT).

## Next

- Caption `<track>` from transcription; backend-generated `thumbnail` assets;
  per-card delete menus; Audience/Connections/Settings pages (unchanged).
