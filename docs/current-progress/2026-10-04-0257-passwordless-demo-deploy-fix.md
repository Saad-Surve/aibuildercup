# Passwordless demo + Cloud Run secret fix

Follow-up to `2026-10-04-0236-readonly-demo-user.md`. Three things: lock the demo account so it
cannot change *anything* (including its own Auth record), hide the copy-token button in the
demo, and fix the failing Cloud Run deploy.

## 1. Demo is now passwordless and self-healing

The shared password (`HabeasCodusDemo!2026`) is gone from the browser and no longer usable.

- **Email/Password sign-in is disabled** on the project (`signIn.email.enabled=false`), so the
  old shared password returns `PASSWORD_LOGIN_DISABLED`.
- **New `POST /api/demo/session`** (`app/api/demo.py`, unauthenticated, disabled unless
  `DEMO_USER_UID` is set) ensures the demo Auth user exists and returns a short-lived Firebase
  **custom token**. The web client signs in with `signInWithCustomToken`; no password ever
  reaches the bundle.
- **Signing works locally and on Cloud Run** because the Admin SDK is now initialised with
  `serviceAccountId` (`app/auth/firebase.py`), so it signs via the IAM signBlob API instead of
  needing a private key. The API SA already has `serviceAccountTokenCreator` on itself
  (`api_sign_blob` in `infra/iam.tf`); the developer accounts were granted the same on the API SA.
- **Self-healing**: `ensure_user` recreates the Auth user if it was deleted. Content lives under
  `users/{uid}` in Firestore/Cloud Storage and is untouched by an Auth deletion, so the next
  "Try the demo" click restores the account. The read-only middleware still rejects every write,
  so the account cannot change any data regardless.
- **Copy-token hidden for read-only**: `app-shell.tsx` renders `CopyTokenButton` only when
  `copyAuthToken && !readOnly`.

## 2. Cloud Run deploy fixed

The `api` job failed with `SecretsAccessCheckFailed` because `youtube-oauth-client-id` /
`youtube-oauth-client-secret` exist in Secret Manager but have **no versions**, and the workflow
attached them unconditionally. That left the live service unhealthy.

- `.github/workflows/deploy.yml` now resolves a `secrets_args` value: attach the OAuth secrets
  only when both have a `latest` version, otherwise `--remove-secrets` them. The API reports
  `OAUTH_NOT_CONFIGURED` when absent.
- Removed the broken secret refs from the running service (`gcloud run services update
  --remove-secrets`) so it is **Ready** again.
- Granted `roles/secretmanager.secretAccessor` to `creator-studio-deployer` and added it to
  `infra/iam.tf`.
- Added `READ_ONLY_USER_UIDS` / `DEMO_USER_UID` to the API deploy env and
  `NEXT_PUBLIC_DEMO_ENABLED` to the web build.

## Structural changes

- Backend: `app/api/demo.py` (new), `app/auth/firebase.py` (`serviceAccountId`,
  `create_custom_token`, `ensure_user`), `app/config.py` (`demo_user_uid`), `app/auth/read_only.py`
  (allow-list `/api/demo/session`), `app/main.py` (demo router).
- Web: `lib/demo.ts` (flag only), `auth-provider.tsx` (custom-token `signInAsDemo`),
  `app-shell.tsx` (hide copy-token in read-only), `.env.local` / `.env.example`.
- Infra/CI/contracts: `.github/workflows/deploy.yml`, `infra/iam.tf`, `infra/RESOURCES.md`,
  `contracts/openapi.yaml` (`POST /api/demo/session`).

## Decisions / gotchas

- `firebase_admin.auth.create_custom_token` fails with plain user ADC **unless** the app is
  initialised with `serviceAccountId`; then it uses IAM signBlob and works locally. This was the
  unlock for dropping the public password.
- Blocking functions only support `beforeCreate`/`beforeSignIn` — there is no `beforeUserDeleted`
  — which is why deletion is handled by recreation on the next demo session rather than blocked.
- The copy-token button always copied `auth.currentUser.getIdToken()`. If it returned your token,
  you were still signed in as yourself (the demo sign-in had not completed); it is now hidden for
  read-only sessions.

## Verification

- `ruff` + `mypy` clean (111 files); `tsc`, `oxlint`, `eslint` (pre-existing `<img>` warning),
  `next build` all pass.
- Live end-to-end (throwaway script, deleted): `POST /demo/session` → 200 token; custom-token
  sign-in yields UID `demoCreatorHabeasCodus`; `/me` → `readOnly: true`; `/projects` → 200;
  `POST /projects` → 403. Old password sign-in now returns `PASSWORD_LOGIN_DISABLED`.
- Cloud Run service `creator-studio-api` is `Ready True` after removing the dead secret refs; the
  conditional resolves to `--remove-secrets` while the secrets are empty.

## Not done / next step

- The YouTube connector stays disabled until a Google OAuth client is created and its values are
  added: `gcloud secrets versions add youtube-oauth-client-id --data-file=-` (and the secret).
  The workflow will then attach them automatically.
- Re-run the `deploy` workflow (it triggers on `.github/workflows/deploy.yml`) to ship the new
  API image + env and the web build with the demo button.
- Uncommitted.
