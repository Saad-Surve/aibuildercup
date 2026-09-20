# Progress — 2026-09-20 15:33 IST

Status: **demo spine started. Backend Firestore layer + Projects API implemented and tested.**

## 1. What I did

Implemented the first backend section from `backend-plan.md` §2/§4/§5 and the "next step" in the
previous note: **Firestore + Projects API**.

New/changed files in `backend/`:

| File | What |
|---|---|
| `app/services/firestore_service.py` | Narrow `FirestoreClient` protocol, real `GoogleFirestoreClient`, pure path builders, `get_firestore_client()` (lru-cached) |
| `app/services/project_service.py` | `ProjectService` CRUD with `ownerUid` checks, offset pagination tokens |
| `app/schemas/projects.py` | `CreateProject`, `UpdateProject`, `Project`, `ProjectList`, `ProjectStatus` |
| `app/schemas/common.py` | `ErrorResponse` / `ErrorDetail` matching the OpenAPI `Error` schema |
| `app/errors.py` | `AppError` hierarchy + `error_body()` envelope builder |
| `app/api/projects.py` | `GET/POST /projects`, `GET/PATCH/DELETE /projects/{projectId}` |
| `app/dependencies.py` | Added `get_project_service()`; `current_user` unchanged |
| `app/main.py` | Registers projects router; added handlers for `AppError`, `HTTPException`, `RequestValidationError` so all errors use the contract envelope |
| `app/providers/llm.py` | Guard `result.text is None` (fixed a pre-existing mypy error) |
| `tests/fakes.py` | In-memory `FakeFirestoreClient` |
| `tests/test_firestore_paths.py`, `test_project_service.py`, `test_projects_api.py` | 25 new tests |

## 2. Structural decisions

- **Firestore is behind a protocol.** Feature code depends on `FirestoreClient` (path-based
  get/set/update/delete/query), not `google.cloud.firestore`. The real adapter is thin; tests use
  an in-memory fake. This mirrors the provider pattern and keeps Firestore out of unit tests.
- **Path builders are pure functions** (`user_path`, `projects_collection_path`, `project_path`)
  and validate segments against `^[A-Za-z0-9_-]{1,128}$`, so a uid/id cannot escape its segment.
- **Ownership is checked twice:** the path is scoped to the caller's uid, and the stored
  `ownerUid` is re-checked before returning. A mismatch is a `404` (not `403`) to avoid leaking
  existence.
- **Soft delete** sets `status=archived`, `archivedAt`, `updatedAt`. Archived docs are filtered out
  of list results in Python (see gotcha below).
- **Timestamps** are generated in the service as `datetime.now(UTC)` and stored by the SDK as
  Firestore Timestamps. This makes the service deterministic and testable.
- **Pagination** uses an opaque base64 offset token. Fine for the MVP; revisit with Firestore
  cursors if a project list ever gets long.
- **Error envelope is now global.** `AppError`/`HTTPException`/validation errors all return
  `{"error": {code, message, requestId, details}}` per `contracts/openapi.yaml`.
- **Schemas use the contract's camelCase field names** directly (no alias generator) so wire and
  storage shapes match the frozen contract.

## 3. Gotchas discovered

- The committed `backend/.venv` was a **Linux venv** (`lib64 -> lib`, `pyvenv.cfg` pointed at
  `/root/.local/share/uv/...`) created under WSL. It cannot run on Windows and `uv run` failed with
  `Access is denied` trying to replace it. Deleted it and ran `uv sync` to create a Windows venv.
  If another agent creates the venv on Linux again, the same breakage returns — prefer not to
  commit `.venv` (it is gitignored, so this was a local-only artifact).
- `ruff` B008 flags `Depends(...)` in defaults. Used `Annotated[T, Depends(...)]` type aliases
  (`UserDep`, `ServiceDep`) instead of `# noqa`.
- Listing projects with an `archivedAt == null` Firestore filter would need another composite
  index (`ownerUid ASC, archivedAt ASC, updatedAt DESC`) that is not in `db-design.md`. Filtered
  archived docs in Python for now to stay on the documented `ownerUid ASC, updatedAt DESC` index.
  This can under-fill a page if many archived docs sit ahead of live ones; acceptable for MVP.

## 4. Verification

- `uv run pytest` → **31 passed** (6 pre-existing + 25 new).
- `uv run ruff check .` → clean.
- `uv run mypy app` → clean (also fixed the one pre-existing `llm.py` error).

No contract change was needed: the Projects endpoints and schemas already existed in
`contracts/openapi.yaml`. No new endpoints were invented.

## 5. Not done / next step

Next in the demo spine: **upload session + assets** (`POST /projects/{projectId}/upload-session`,
`POST /projects/{projectId}/assets/{assetId}/complete`).

- Add a `storage_service.py` with a `StorageClient` protocol + real GCS adapter and signed-URL
  generation; validate MIME/size before issuing the URL.
- Add `asset_service.py` (Firestore `assets/{assetId}` per `db-design.md`).
- Add `app/api/uploads.py`; update `contracts/openapi.yaml` only if the shape changes.
- Add a `job_service.py` and the `transcribe` job stub, then the `transcript` endpoint, before the
  timeline UI (workstream A) can consume it.
- Still deferred: Firebase emulator integration tests, seed script, real GCS verification on
  `/complete`.
