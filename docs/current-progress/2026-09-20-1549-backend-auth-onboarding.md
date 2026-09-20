# Progress — 2026-09-20 15:49 IST

Status: **auth + onboarding + persona implemented on the backend, tested, and running.**

## 1. What I did

Implemented the `/me`, `/onboarding`, and `/persona` surface from `api-design.md` §2/§3 and
`contracts/openapi.yaml`. Also added the Cloud Storage service layer, which onboarding needs and
uploads will reuse.

New/changed files in `backend/`:

| File | What |
|---|---|
| `app/services/paths.py` | **New** shared pure path builders + `safe_segment`; moved Firestore paths here, added persona doc/object paths |
| `app/services/firestore_service.py` | Re-exports paths; keeps the `FirestoreClient` protocol and real adapter |
| `app/services/storage_service.py` | **New** `StorageClient` protocol, real GCS adapter (`upload_text`, `download_text`, `object_exists`, `signed_download_url`), object-path validation |
| `app/services/user_service.py` | **New** lazy `users/{uid}` creation, onboarding state get/save/complete, persona metadata |
| `app/services/persona_service.py` | **New** persona generation, storage, versioned edits, `personaRevisions` records |
| `app/schemas/users.py`, `onboarding.py`, `persona.py` | **New** contract-matching models |
| `app/api/users.py`, `app/api/onboarding.py` | **New** routers (`/me`, `/onboarding`, `/onboarding/complete`, `/persona`) |
| `app/dependencies.py` | `AuthenticatedUser` now carries `display_name`/`picture`; added `get_user_service`, `get_persona_service` |
| `app/config.py` | Added the model registry (`model_reviewer`, `model_orchestrator`, `model_image`, `model_video`, `model_stt`) |
| `app/providers/__init__.py` | Added cached `get_providers()` singleton |
| `app/main.py` | Registers the users + onboarding routers |
| `.env.example` | Documents the model-registry env vars |
| `tests/fakes.py` | Added `FakeStorageClient` and `StubLlmProvider` |
| `tests/test_user_service.py`, `test_persona_service.py`, `test_onboarding_api.py` | 18 new tests |

## 2. Structural decisions

- **Auth is unchanged in spirit**: Firebase ID token → `current_user`. The dataclass gained
  optional `display_name`/`picture` (from the token's `name`/`picture` claims) so `/me` can seed
  the profile. Fields have defaults, so existing callers/tests still work.
- **User doc is created lazily** on the first authenticated request (`ensure_user`). The frontend
  never bootstraps it. `displayName`/`email`/`photoUrl` are refreshed from the token when they
  change.
- **Onboarding answers live on the user doc** under `onboarding.answers` (merged per step), with
  `status` and `currentStep`. `completed` never regresses to `in_progress` if the user edits after
  finishing. This is a small extension beyond `db-design.md`, which only listed status/step, but
  `OnboardingState` in the contract requires returning `answers`.
- **Persona generation goes through the LLM provider** (`model_orchestrator`, prompt
  `persona-v1`), then writes `users/{uid}/profile/persona.md` plus an immutable revision object
  `users/{uid}/profile/revisions/persona-v{n}.md`, and a `personaRevisions` doc.
- **Offline fallback**: if there is no cassette (`CassetteMiss`) or the LLM call raises, the
  service falls back to a deterministic `build_persona_markdown(answers)` template. This keeps
  onboarding working with no network/credentials, per the mock-and-seed goal. The exception is
  logged.
- **Persona edits are optimistic-concurrency checked**: `expectedVersion` must equal the stored
  version or the API returns `409` with code `PERSONA_VERSION_CONFLICT` (contract `Conflict`).
- **Storage paths are validated** the same way as Firestore paths; every id must be one safe
  segment. Only object paths are stored, never signed URLs.
- **Model ids are config-driven**, not hardcoded in services/agents (backend-plan §1).

## 3. Gotchas discovered

- **The OneDrive-hosted venv keeps dehydrating files.** This session, `dotenv`, then mypy's
  compiled module, then `google.protobuf` went missing from `.venv`. Symptom: `ModuleNotFoundError`
  for a package that `uv pip list` says is installed. Fix: stop any process using the venv, then
  `uv sync --reinstall`. If it recurs, consider pointing `UV_PROJECT_ENVIRONMENT` at a path
  outside OneDrive.
- **mypy can't resolve `from google.cloud import storage`** because `google-cloud-storage` ships no
  `py.typed` while `google-cloud-firestore` does, so `google.cloud` is partially typed and mypy
  reports `attr-defined`. Added `# type: ignore[attr-defined]` on that one import.
- **Firestore dotted update keys are not portable to the test fake.** All user/onboarding/persona
  mutations read-modify-write the whole nested map instead of using `"onboarding.status"` style
  keys, so the real client and the in-memory fake behave identically.
- The backend server must be stopped before `uv sync` can replace `uvicorn.exe` (file lock).

## 4. Verification

- `uv run pytest` → **49 passed** (31 before + 18 new).
- `uv run ruff check .` → clean.
- `uv run mypy app` → clean (31 source files).
- Server restarted detached on `127.0.0.1:8080`. `/healthz` ok; `/me` and `/onboarding` return the
  contract `UNAUTHORIZED` envelope without a token; `/openapi.json` lists `/me`, `/onboarding`,
  `/onboarding/complete`, `/persona` alongside the project routes.

No contract change was needed — every endpoint already existed in `contracts/openapi.yaml`.
Not implemented (and not in the contract): `/persona/revisions`, `/persona/suggestions/...`.

## 5. Not done / next step

Continue the demo spine: **upload session + assets** (`POST /projects/{projectId}/upload-session`,
`POST /projects/{projectId}/assets/{assetId}/complete`).

- `storage_service` already exists; add signed *upload* URL support (currently only download) and
  MIME/size validation.
- Add `asset_service.py` for `projects/{projectId}/assets/{assetId}` per `db-design.md`.
- Then `job_service.py` + the `transcribe` job stub + `GET /projects/{projectId}/transcript`, so
  workstream A can build the timeline.
- Deferred: Firestore emulator integration tests, `scripts/seed.py --demo` (now closer, since
  `users/{uid}` and persona shapes exist), persona revision listing/approval endpoints.
