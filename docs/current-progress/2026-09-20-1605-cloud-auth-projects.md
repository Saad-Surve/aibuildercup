# Progress — 2026-09-20 16:05 IST

Status: **auth + projects cloud configuration is applied. Firestore index READY, rules released,
Google sign-in verified. Local ADC still pending (one browser step for the user).**

## 1. What I did

Provisioned the cloud-side pieces that auth and projects need, using the owner account
(`aibuildercup@gmail.com`).

| Thing | Result |
|---|---|
| Firestore composite index | `projects`: `ownerUid` ASC, `updatedAt` DESC (COLLECTION scope) — **READY** |
| Firestore security rules | `firestore.rules` released as `cloud.firestore` — deny all direct client access |
| Firebase Auth | Verified: `defaultSupportedIdpConfigs/google.com` `enabled=true`; authorized domains `localhost`, `habeas-codus.firebaseapp.com`, `habeas-codus.web.app` |
| Backend CORS | Added `CORSMiddleware` + `CORS_ALLOWED_ORIGINS` so the web app can call the API cross-origin |

Files added/changed:

| File | What |
|---|---|
| `firestore.rules` | **New** deny-all client rules (repo root; shared by Terraform and the Firebase CLI) |
| `firebase.json`, `.firebaserc` | **New** so `firebase deploy --only firestore:rules` works once firebase-tools is fixed |
| `infra/firestore_indexes.tf` | **New** Terraform for the projects composite index |
| `infra/firestore_rules.tf` | **New** Terraform for the ruleset + `cloud.firestore` release |
| `infra/RESOURCES.md` | Documented the index, rules, and the applied commands |
| `backend/app/config.py` | Added `cors_allowed_origins` |
| `backend/app/main.py` | Added `CORSMiddleware` |
| `backend/.env.example` | Documented `CORS_ALLOWED_ORIGINS` |
| `backend/tests/test_cors.py` | **New** 2 tests (allowed origin + unknown origin rejected) |

## 2. Why direct apply instead of `terraform apply`

Terraform is not installed on this workstation, and the engineer account cannot impersonate the
`terraform@habeas-codus` SA. The owner account was used directly via `gcloud` and the Firebase
Rules REST API. The Terraform files were still added so `terraform apply` converges to the same
state later (import may be needed for the two Firestore resources).

The Firebase Rules API was used directly because the global `firebase-tools` install is broken
(`Cannot find module .../firebase-tools/lib/bin/firebase.js`). No `firebase deploy` was possible.

## 3. Permissions / gotchas discovered

- The engineer account `ankitmishra21022003@gmail.com` is **Viewer + Cloud Run Developer +
  Artifact Registry Writer + Logs Viewer + SA User**. That is *not* enough to create Firestore
  indexes or deploy rules. The owner account is required, or the engineer needs
  `roles/datastore.indexAdmin`, `roles/firebaserules.admin`, and
  `roles/serviceusage.serviceUsageConsumer`.
- Calls to Identity Toolkit / Firebase Rules REST need the `x-goog-user-project: habeas-codus`
  header when using user credentials; otherwise they fail with a misleading "ADC quota project"
  error.
- **The backend needs Application Default Credentials to verify Firebase ID tokens.** With no ADC,
  `verify_id_token` raises `DefaultCredentialsError` before it even looks at the token. On Cloud
  Run the attached runtime SA supplies credentials automatically; locally you must run
  `gcloud auth application-default login`.
- The interactive `gcloud auth application-default login` launched from inside a tool returned a
  browser 400 and was aborted. Run it from a normal terminal.

## 4. Verification

- `uv run pytest` → **51 passed** (49 + 2 CORS).
- `uv run ruff check .` → clean; `uv run mypy app` → clean.
- `gcloud firestore indexes composite list` → the `projects` index is `READY`.
- Firebase Rules `releases/cloud.firestore` points at the new deny-all ruleset (verified via
  `GET /v1/projects/habeas-codus/releases/cloud.firestore`).
- Identity Toolkit config confirms Google sign-in enabled and the authorized domains.

## 5. Not done / next step

- **User action:** run `gcloud auth application-default login` in a normal terminal so the local
  backend can verify Firebase tokens. Then `GET /me` with a real Firebase ID token works end to end.
- Optional: install firebase-tools (`npm i -g firebase-tools`) to use `firebase deploy`.
- Optional: install Terraform and import the two Firestore resources so state matches.
- Next feature work is still the upload session + assets, then transcript, per the previous note.
- The API is **not deployed to Cloud Run yet**. Deploying it is the next cloud step; it needs
  `roles/run.admin` (for `--allow-unauthenticated`) or an owner-set invoker binding.
