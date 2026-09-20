# Progress — 2026-09-20 20:50 IST

Status: **first vertical slice of the project workspace is in. You can create a project, upload a
video directly to Cloud Storage, and the upload queues a transcription job.** Backend + web,
tests/lint/typecheck/build all green.

## 1. What I did

The user asked to start "the main part — the project part". Auth, onboarding, and account deletion
were already done. I built the smallest end-to-end path to the workspace: **project list + create +
direct video upload → queued transcribe job**.

### Backend (`backend/`)

| File | What |
|---|---|
| `app/services/paths.py` | `assets_collection_path`, `asset_path`, `jobs_collection_path`, `job_path`, `source_object_path` (validates the extension) |
| `app/services/firestore_service.py` | Added `query_collection_group` to the protocol + real client; re-exports the new path builders |
| `app/services/storage_service.py` | Added `signed_upload_url` (GCS V4 signed PUT) to the protocol + real client |
| `app/services/asset_service.py` | New. Upload session (MIME/size validation, pending asset doc, signed URL), `complete_upload` (verify object exists → mark uploaded → project processing → queue transcribe job), `list` |
| `app/services/job_service.py` | New. `create` (idempotent per `idempotencyKey`), `get` by id via collection-group query |
| `app/services/project_service.py` | `_to_project` now maps `progress`; added `mark_processing` |
| `app/schemas/assets.py`, `app/schemas/jobs.py`, `app/schemas/common.py` | New asset/job schemas; `AcceptedJob` |
| `app/schemas/projects.py` | Added `ProjectProgress` and `Project.progress` |
| `app/api/uploads.py`, `app/api/jobs.py` | New routers; registered in `main.py` |
| `app/dependencies.py` | `get_asset_service`, `get_job_service` |
| `.env.example` | `MAX_UPLOAD_SIZE_BYTES`, `UPLOAD_URL_TTL_SECONDS` |

New endpoints: `POST /api/projects/{projectId}/upload-session`,
`GET /api/projects/{projectId}/assets`,
`POST /api/projects/{projectId}/assets/{assetId}/complete`, `GET /api/jobs/{jobId}`.

### Contract (`contracts/openapi.yaml`)

- Added `GET /projects/{projectId}/assets`, `Asset`, `AssetList`, `UploadSessionRequest`.
- `Job` now has `createdAt`/`updatedAt`; `Project` now has `progress`.
- The upload-session request body is now a named schema instead of inline.

### Web (`web/`)

| File | What |
|---|---|
| `src/lib/types.ts` | `Project`, `Asset`, `UploadSession`, `Job`, `AcceptedJob` + statuses |
| `src/lib/projects.ts` | API helpers, `validateVideoFile`, `uploadToStorage` (XHR for progress), `formatBytes` |
| `src/mocks/handlers.ts` | In-memory handlers for the whole flow, including the mock signed upload URL |
| `src/components/ui/dialog.tsx` | New Base UI dialog primitive (modelled on `alert-dialog`) |
| `src/components/projects/*` | `CreateProjectDialog`, `ProjectCard`, `ProjectStatusBadge`, `VideoDropzone`, `ProcessingStatusCard`, `ProjectWorkspace` |
| `src/app/(app)/projects/page.tsx` | List + create + empty state |
| `src/app/(app)/projects/view/page.tsx` | Workspace; reads `?projectId=` |
| `src/app/(app)/dashboard/page.tsx` | Recent projects instead of the placeholder |
| `src/components/layout/app-shell.tsx` | Projects nav enabled; active state matches sub-routes |

## 2. Structural decisions

- **Jobs are stored under the project** (`users/{uid}/projects/{pid}/jobs/{jid}`) per `db-design.md`,
  but the contract's `GET /jobs/{jobId}` is project-agnostic. I solved this by denormalising
  `jobId` into the job document and using a Firestore **collection-group** query filtered on that
  single field (auto-indexed, no composite index). `ownerUid` is re-checked in Python.
- **Idempotency** for job creation queries the project's `jobs` collection by `idempotencyKey`
  (single-field equality, no composite index). `complete_upload` is therefore safe to retry and
  returns the original job.
- **Upload is two safety layers**: the API validates MIME + size *before* issuing the URL, and
  `complete` verifies the object actually exists in the bucket before recording it. `UPLOAD_NOT_FOUND`
  (400) otherwise.
- **Allowed source types** are `video/mp4`, `video/quicktime`, `video/webm`, `video/x-m4v`, mapped
  to the storage extension. Cap is `MAX_UPLOAD_SIZE_BYTES` (500 MB), matching
  `users/{uid}.limits.maxVideoSizeBytes`.
- **Project `progress` was added to the API contract.** `db-design.md` already stores it; exposing it
  lets the workspace show a state after a page reload (when the client no longer holds the job id).
- **No Pub/Sub publish yet.** `complete_upload` only creates the queued job. The transcribe worker and
  the `object finalized` notification are the next slice; publishing to a topic with no subscriber
  would be dead weight.

## 3. Gotchas discovered

- **`web/` is a static export (`output: "export"`), so `/projects/[projectId]` is impossible.**
  Next refuses dynamic routes without `generateStaticParams`, and project ids only exist at runtime.
  The workspace lives at the static route `/projects/view?projectId=...` instead. If a prettier URL
  is ever wanted, it needs a hosting rewrite *and* a client router that knows the path — more trouble
  than it is worth for the hackathon.
- `useSearchParams` must be wrapped in a `Suspense` boundary or the export build fails; the
  `projects/view` page does this.
- The fake Firestore in `tests/fakes.py` needed a `query_collection_group` that matches a
  `/<collection>/` segment anywhere in the path (collection-group semantics), not just a prefix.

## 4. Verification

- Backend: `uv run pytest` → **91 passed** (was 64). `uv run ruff check .` clean.
  `uv run mypy app` clean.
- Web: `bun run lint` (oxlint) clean. `bun run lint:eslint` clean. `bun run format:check` clean.
  `bun run build` succeeds (10 static pages, incl. `/projects` and `/projects/view`).
- Manual browser smoke was not run; the upload path is covered by API tests and the MSW handlers.

## 5. Not done / next step

The job sits in `queued` forever because nothing consumes it yet. Next, in order:

1. **Transcription worker + provider.** `POST /projects/{projectId}/transcript/regenerate` exists in
   the API design; add `providers/stt.py` (real + cassette), the `transcribe` worker, transcript
   Firestore docs (`transcripts/{id}` + `segments`), and flip the project to `ready`.
2. **Real trigger.** Wire the Cloud Storage `object finalized` notification (or a Pub/Sub publish in
   `complete_upload`) so processing also starts if the client never calls `/complete`.
3. **`GET /projects/{projectId}/transcript`** so the timeline UI can render.
4. **Analysis + heatmap** (the flagship) then the timeline/heatmap workspace UI.
5. Deferred from before: Firebase emulator integration tests, seed script (`scripts/seed.py`),
   real-GCS verification in CI, and project soft-delete object cleanup.
