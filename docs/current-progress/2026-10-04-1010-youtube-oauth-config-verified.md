# YouTube connector: OAuth config verified live (local + deployed)

## What I did

Verified the user's console/setup work end to end and fixed the one gap found.

**Verified**
- Secret Manager: `youtube-oauth-client-id` and `youtube-oauth-client-secret` each have version 1
  `enabled`.
- Local config (`backend/.env`): client id/secret present, OAuth client builds, redirect resolves to
  `http://localhost:8080/api/connections/youtube/oauth/callback`, scopes are the expected six
  (openid, userinfo.email, youtube.readonly, youtube.upload, youtube.force-ssl, yt-analytics.readonly).
- Firestore: `oauthStates.state` field override exists with `COLLECTION_GROUP` ASCENDING index
  `READY` (plus the `jobs.jobId` exemption and the projects composite index).
- Deployed env: `API_PUBLIC_BASE_URL=https://creator-studio-api-3sim77rugq-uc.a.run.app`,
  `WEB_BASE_URL=https://habeas-codus.web.app`.

**Fixed**
- The deployed Cloud Run service had **no OAuth secrets attached** (the user added the secret
  versions but had not redeployed, so the deploy workflow's conditional had not run). Attached them
  directly with `gcloud run services update --update-secrets=GOOGLE_OAUTH_CLIENT_ID=…,GOOGLE_OAUTH_CLIENT_SECRET=…`
  → new revision `creator-studio-api-00079-vfk`, 100% traffic. Env now shows both as `secretKeyRef`.

**Live smoke test**
- `GET /api/healthz` → 200.
- `GET /api/connections/youtube/oauth/callback?state=bogus&code=bogus` → 302 to
  `https://habeas-codus.web.app/profile?youtube=error&reason=This connection link is no longer valid.`
  A 302 (not 500) proves the unauthenticated callback route runs the Firestore collection-group
  query successfully on the deployed service.

## Gotchas

- The Cloud Run URL has two forms (`…-3sim77rugq-uc.a.run.app` and
  `…-538724167565.us-central1.run.app`). The OAuth redirect registered on the client and the
  service's `API_PUBLIC_BASE_URL` both use the `-uc.a.run.app` form; keep them in sync.
- Next CI deploy will re-apply the secrets via `--set-secrets` (versions now exist), so the manual
  `--update-secrets` causes no drift.

## Not done / next step

- Browser test still to run: Profile → Connected channels → **Connect a Google account**, then a
  project → **Publish to YouTube**. Uploads stay private until the OAuth app passes YouTube's audit.
- Then pick next work: native Bluesky/Mastodon connectors, or the unused social-sync → BigQuery
  analytics pipeline.
