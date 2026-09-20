# Progress — 2026-09-20 20:55 IST

Status: **`/me` 404 fixed. It was the local API base URL missing `/api`, not the manual Firestore
cleanup.** No backend change was needed.

## 1. What was reported

After manually deleting the leftover GCS objects and Firestore data (from the earlier
delete-account bug), `GET /me` started returning 404.

## 2. Root cause

The request never reached the API. The backend mounts every router under `/api`
(`app/main.py`, `include_router(..., prefix="/api")`), and Firebase Hosting rewrites only
`/api/**` to Cloud Run. The web client built its URL as
`NEXT_PUBLIC_API_BASE_URL + path` with no normalisation, and the local `web/.env` set
`NEXT_PUBLIC_API_BASE_URL=http://localhost:8080` (no `/api`). So `apiFetch("/me")` called
`http://localhost:8080/me`, which is a real 404.

Evidence:

- `uvicorn` + `curl`: `http://localhost:8080/me` → 404, `http://localhost:8080/api/me` → 401.
- Cloud Run logs: `GET /api/me` → 200, `GET /me` → 404.
- Deployed config was already correct: repo variable `API_URL=https://habeas-codus.web.app/api`,
  and `https://habeas-codus.web.app/api/me` → 401 (no token).

The manually deleted documents were a red herring: `UserService.ensure_user` recreates
`users/{uid}` on the first authenticated request, so `/api/me` works after a wipe. If the Firebase
Auth account was also removed, the next Google sign-in recreates it.

## 3. Fix

- New `web/src/lib/api-base.ts`: reads `NEXT_PUBLIC_API_BASE_URL`, strips trailing slashes, and
  appends `/api` when the suffix is missing. One source of truth for the base URL.
- `web/src/lib/api-client.ts` and `web/src/mocks/handlers.ts` now import `API_BASE_URL` from it
  instead of each building the URL from the raw env value.

This makes both `http://localhost:8080` and `https://habeas-codus.web.app/api` resolve to a working
API root, so the env file did not need editing.

## 4. Verification

- Web: `bun run lint` (oxlint), `bun run lint:eslint`, `bun run format:check` all clean.
- `bun run build` succeeds; the emitted chunk shows the base normalised to
  `http://localhost:8080/api`.
- Backend untouched by this fix; the previous run's 91 tests / ruff / mypy still apply.

## 5. Next step

Unchanged from the previous note: the transcribe worker + STT provider and the transcript endpoint,
then analysis/heatmap. Since the user wiped dev data, a fresh sign-in will land on onboarding again;
after that, creating a project exercises the upload slice.
