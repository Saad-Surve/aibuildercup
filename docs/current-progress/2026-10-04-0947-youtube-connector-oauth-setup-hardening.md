# YouTube connector: OAuth console setup + connector hardening

## What I did

Prepared the YouTube connector for the console OAuth setup and closed the real gaps found in the
earlier audit. The user is doing the GCP console steps; the code is ready for the credentials.

**Config**
- Appended the OAuth block to `backend/.env` with **placeholders** (client id/secret blank for the
  user to fill): `WEB_BASE_URL`, `API_PUBLIC_BASE_URL`, `GOOGLE_OAUTH_CLIENT_ID`,
  `GOOGLE_OAUTH_CLIENT_SECRET`, `OAUTH_TOKEN_ENCRYPTION_KEY=local-dev-token-key`.

**Code**
- **Account deletion now revokes OAuth grants.** `ConnectionService.revoke_all(owner_uid)` is
  best-effort (never raises; tolerates an unconfigured OAuth client and per-connection failures).
  `UserService.delete_account` calls it before the storage prefix + Firestore tree delete, so the
  tokens are not destroyed without revoking them at Google. `UserService` takes an optional
  `connections=` dependency; `get_user_service` wires `get_connection_service()`.
- **Corrected the stale quota comment** in `connectors/youtube.py`: 2026 YouTube gives
  `videos.insert` its own bucket of 100 uploads/day (cost 1); `thumbnails.set` = 50 units and
  `captions.insert` = 400 units from the shared 10,000 units/day pool.
- **Publish staging guard.** New `PUBLISH_MAX_STAGE_BYTES` (default 2 GB) caps the worker's local
  temp-disk staging separately from the 8 GB business limit; the worker uses
  `min(publish_max_source_bytes, publish_max_stage_bytes)` and fails fast instead of hitting
  ENOSPC on Cloud Run's default disk. Documented in `.env.example`.

## Verification

- `uv run ruff check .` clean; `uv run mypy app` clean (111 files).

## Decisions / gotchas

- **Local and deployed tokens are not interchangeable.** Local encrypts with a Fernet key derived
  from `OAUTH_TOKEN_ENCRYPTION_KEY`; production uses Cloud KMS (`user-token-key`, and the API SA
  already has `roles/cloudkms.cryptoKeyEncrypterDecrypter`). A connection made locally will read as
  absent in production (needs reconnect) and vice versa.
- Deploy is already wired: `deploy.yml` attaches `youtube-oauth-client-id`/`-secret` from Secret
  Manager **only when a version exists** (empty secrets otherwise), and sets `API_PUBLIC_BASE_URL`
  and `WEB_BASE_URL`. The secrets are declared empty in `infra/secrets.tf`.
- The `oauthStates.state` collection-group index (`infra/firestore_indexes.tf`) must exist in the
  project or the unauthenticated callback fails with FAILED_PRECONDITION.

## Not done / next step

- **User (console):** OAuth consent screen (External) with the six scopes + test users; create the
  Web OAuth client; register `http://localhost:8080/api/connections/youtube/oauth/callback` and the
  Cloud Run callback `https://<api-url>/api/connections/youtube/oauth/callback`; paste id/secret
  into `backend/.env`; for deployed, add the two Secret Manager versions and apply the Firestore
  index. Then connect a channel and run the Part 7b publish flow.
- Then: pick the next connector work (native Bluesky/Mastodon, or the unused social-sync →
  BigQuery analytics pipeline).
