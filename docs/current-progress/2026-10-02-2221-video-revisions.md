# Video revisions: upload a new cut of the project's video

## What I did

A project now keeps **one video with many revisions**. The creator can upload a new
revision at any time from the source-video card; it becomes the project's active source
and is transcribed automatically. Every earlier revision, its transcripts, and its
analysis runs are retained, so a review always stays attributable to the cut it graded.
After the new transcript lands, the review panel nudges the user to re-run the analysis.

Decisions confirmed with the user before building: auto-transcribe a new revision (then
offer analysis), retain all revisions, and ship backend + frontend + contracts together.

## Changes

### Contract (`contracts/openapi.yaml`)

- `Asset` gained `revision: integer | null`.
- `Project` gained `sourceAssetId`, `sourceRevision`, `revisionCount`.
- New `GET /api/projects/{projectId}/revisions` → `RevisionList` (`Revision` has
  `revision`, `assetId`, `status`, `mimeType`, `sizeBytes`, `durationMs`, `storagePath`,
  `isActive`, `createdAt`).
- Upload endpoints are unchanged: a revision is just another `source_video` upload.

### Backend

- `schemas/assets.py` — `Asset.revision`; new `Revision` / `RevisionList`.
- `schemas/projects.py` — `Project.sourceAssetId` / `sourceRevision` / `revisionCount`.
- `services/project_service.py` — project docs carry `sourceRevisionCounter` and
  `sourceRevision`; `mark_processing` takes an optional `revision` and only moves the
  counter forward, so re-completing an older upload cannot roll the active revision back.
- `services/asset_service.py` — `create_upload_session` numbers each upload
  (`max(counter, existing sources) + 1`, so legacy projects with unrevisioned sources
  never collide); `queue_transcription` and `retranscribe_source` record the active
  revision; new `list_revisions` (newest first, active flagged, legacy sources numbered by
  upload order). Renamed `AssetService.list` → `list_assets` (the old name shadowed the
  `list` builtin in a method annotation and broke mypy).
- `api/uploads.py` — `GET /projects/{projectId}/revisions`.

### Frontend

- `lib/types.ts` / `lib/projects.ts` — revision fields and `listRevisions`.
- New `components/projects/video-revisions.tsx` — active-revision badge, history dialog,
  and a "New revision" dialog wrapping the existing `VideoDropzone`.
- `components/projects/project-workspace.tsx` — mounts `VideoRevisions` in the source
  card header and shows `Revision N · mimeType`; local-only fallback asset gets
  `revision: null`.
- `components/projects/review-panel.tsx` — banner when the newest run's `transcriptId`
  differs from the active transcript ("A newer transcript is ready…").
- `components/projects/video-dropzone.tsx`, `hooks/use-project-events.ts` — invalidate
  the `["revisions", projectId]` query on upload and on reconnect.

### Docs

- `docs/technical-design/db-design.md` — project + asset revision fields.
- `docs/technical-design/api-design.md` — revisions route and a "Revisions" section.
- `docs/technical-design/frontend-plan.md` — upload section describes `VideoRevisions`.

## Structural changes

- Firestore: project docs gain `sourceRevision` and `sourceRevisionCounter`; `source_video`
  assets gain `revision`. No new collections, buckets, or third-party records — every
  revision is an asset under `users/{uid}/projects/{projectId}/...`, so the existing
  recursive project/account delete covers them with no extra wiring.
- API: one new read endpoint and three additive schema fields; nothing existing changed
  shape, so the web client cannot drift.

## What I decided / discovered

- Reusing the existing upload + auto-transcribe pipeline means a revision needs no new
  job type. The new asset's idempotency key (`transcribe-{project}-{assetId}-v1`) is
  naturally fresh, and both the `complete` and GCS-finalized paths converge on it.
- The active revision is the project's `sourceAssetId`, already used by captions and
  `retranscribe_source`; I made `retranscribe_source` prefer it over "newest" so a legacy
  project re-transcribes the video it actually points at.
- Legacy projects: source assets uploaded before this feature have no `revision` and the
  project has no counter. Numbering accounts for existing sources on upload and falls back
  to upload order on read, so no collision or gap.
- `AssetService.list` shadowed the `list` builtin in a `-> list[Revision]` annotation
  once `list_revisions` was defined after it (mypy `valid-type`). Renamed to `list_assets`.

## Verification

- `uv run ruff check .` clean; `uv run mypy app` clean (76 files).
- `contracts/openapi.yaml` parses with `yaml.safe_load`; new path/schemas present.
- `web`: `bunx tsc --noEmit` clean, `bun run lint` (oxlint) clean, `bunx eslint` on the
  changed files clean, `oxfmt --check` clean, `bun run build` succeeds.

## Not done / next step

- Uncommitted. Say the word and I'll commit + push.
- Optional follow-ups: expose a per-revision transcript/analysis link in the history
  dialog (the data exists via `transcriptId`/`sourceAssetId` but is not joined); allow
  re-activating an older revision; and consider pruning `pending` assets from abandoned
  upload sessions if that ever becomes noisy.
