# Video revisions: re-activate an older revision + per-revision history

## What I did

Follow-up to `2026-10-02-2221-video-revisions.md`. Two additions:

1. **Re-activate an earlier revision.** `POST /projects/{projectId}/revisions/{assetId}/activate`
   points the project back at a revision. If that revision already has a transcript, the
   newest one becomes the active transcript and the project is `ready`; otherwise a fresh
   transcribe job is queued and its `jobId` is returned. Nothing is deleted, so switching
   back and forth is lossless.
2. **Per-revision transcript/analysis join.** `GET /revisions` now joins each revision to
   its newest transcript (`transcriptId` / `transcriptVersion`) and its `analysisRunCount`,
   and the history dialog shows them.

## Changes

### Contract (`contracts/openapi.yaml`)

- `Revision` gained `transcriptId`, `transcriptVersion`, `analysisRunCount`.
- New `POST /api/projects/{projectId}/revisions/{assetId}/activate` → `RevisionActivation`
  (`assetId`, `revision`, `transcriptId`, `jobId`).

### Backend

- `schemas/assets.py` — `Revision` join fields; new `RevisionActivation`.
- `services/asset_service.py` — `list_revisions` queries `transcripts` and `analysisRuns`
  once and groups by `sourceAssetId`; new `activate_revision` (returns the activation and
  an optional queued `Job`).
- `api/uploads.py` — activate route; schedules the transcribe worker when a job was queued.

### Frontend

- `lib/types.ts` / `lib/projects.ts` — join fields, `RevisionActivation`, `activateRevision`,
  and a new `pickSourceAsset(assets, activeAssetId)` helper.
- `components/projects/video-revisions.tsx` — history rows show `Transcript vN` and review
  count; non-active revisions get an **Activate** button with pending state.
- `components/projects/{project-workspace,project-card,transcript-editor}.tsx` — now select
  the source video via `pickSourceAsset` / `project.sourceAssetId` instead of "first source
  video". This is load-bearing once an older revision is active: `listAssets` is sorted
  newest-first, so "first source" would otherwise keep showing the newest cut after a
  switch-back.

### Docs

- `docs/technical-design/api-design.md` — activate route + joined fields.
- `docs/technical-design/frontend-plan.md` — history/activation sentence.

## Structural changes

- One new write endpoint (`activate`) and three additive `Revision` fields. No new
  collections, no new job type (activation reuses `transcribe`), no delete-path changes.

## What I decided / discovered

- Activation reuses the `transcribe` job with a per-transcript-version idempotency key
  (`transcribe-{project}-{assetId}-r{n}`), the same key `retranscribe_source` uses, so a
  double click before the transcript lands stays idempotent.
- Switching the active source without switching the active transcript would leave the
  heatmap describing a different cut, so activation selects that revision's newest
  transcript (or generates one). The review panel's existing "newer transcript" nudge then
  covers re-running analysis.
- The frontend had four "first `source_video`" selections. All four now prefer the
  project's `sourceAssetId`; without this, re-activating an older revision would still play
  and caption the newest one.

## Verification

- `uv run ruff check .` clean; `uv run mypy app` clean (76 files).
- `contracts/openapi.yaml` parses; activate path, `RevisionActivation`, and join fields present.
- Web `tsc --noEmit`, `oxlint`, `eslint` (0 errors; one pre-existing `<img>` warning),
  `oxfmt --check`, and `next build` all pass.

## Not done / next step

- Uncommitted. Say the word and I'll commit + push.
- Possible follow-up: deep-link the review panel to a revision's analysis run (the run id
  is not exposed on `Revision` yet, only the count).
