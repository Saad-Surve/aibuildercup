# YouTube connector + end-to-end publishing

## What I did

Built the first real connector (YouTube) and a complete project → YouTube publish pipeline,
with a Gmail-account picker on connect.

**Backend**

- **OAuth (authorization code + PKCE).** `app/services/oauth_service.py` is the only code that
  talks to Google's OAuth endpoints (`requests`, no `google-auth-oauthlib`). `prompt=consent
  select_account` + `access_type=offline` gives the Gmail account chooser and a refresh token.
- **Connected accounts.** `app/services/connection_service.py` creates one connection per
  channel, stores encrypted tokens in a sibling secret doc, refreshes access tokens in place,
  marks `needs_reauth` on a rejected refresh, and revokes+deletes on disconnect.
- **Token encryption.** `app/services/token_cipher.py` — Cloud KMS (`user-token-key`) in prod,
  a passphrase-derived Fernet cipher locally (`OAUTH_TOKEN_ENCRYPTION_KEY`) so no KMS grant is
  needed for the demo.
- **YouTube connector.** `app/connectors/youtube.py` wraps `googleapiclient`: `channels.list`,
  resumable `videos.insert` with byte progress, `thumbnails.set`, and `captions.insert`. No
  feature code imports the Google SDK.
- **Publishing.** `app/services/publish_service.py` freezes the chosen video (source / burned
  caption render / dub), thumbnail version, and the SRT/VTT built from the transcript into a
  `Publish` doc at create time. `app/workers/publish_worker.py` stages the video to a temp file,
  uploads it (reporting progress), sets the thumbnail, uploads captions, then records the
  YouTube video id/url. A thumbnail rejection does not fail an already-uploaded video.
- **API.** `GET/POST/DELETE /connections…`, `GET/POST /projects/{id}/publishes`,
  `GET/DELETE /projects/{id}/publishes/{publishId}`, `POST …/retry`. All ownership-checked.
- **Infra.** Added the `oauthStates.state` collection-group index the unauthenticated callback
  needs (`infra/firestore_indexes.tf`). The deploy workflow now passes the OAuth id/secret from
  Secret Manager and the web/API base URLs to Cloud Run.

**Web**

- New **Publish to YouTube** studio module (`publishing-module.tsx`): channel picker, video
  picker (source / captioned / dubbed), thumbnail grid, caption format/language, listing form,
  publish history with live progress, retry, and “Open on YouTube”.
- `youtube-connections.tsx` — reusable connect/list/sync/disconnect card (also on the Profile
  page). “Connect a Google account” opens Google's account chooser; the connected Gmail is shown
  on each channel.
- New `web/src/lib/connections.ts` and `web/src/lib/publishes.ts`, types in `types.ts`.
- **Follow-up:** added a dedicated `/connections` page and flipped the sidebar `Connections`
  entry to `ready: true` (it was hidden). The connection card now lives on Profile, on
  `/connections`, and inside the publish module.

## Structural changes

- New Firestore paths: `users/{uid}/connections/{id}`, `connectionSecrets/{id}`,
  `oauthStates/{state}`, `projects/{pid}/publishes/{id}` (all under the user/project subtree, so
  existing recursive delete covers them).
- New `JobType.publish`.
- `contracts/openapi.yaml` and `contracts/firestore.md` updated; `backend/.env.example`,
  `LOCAL_SETUP.md` (new Part 7b), and `infra/firestore_indexes.tf` updated.
- `pyproject.toml`: `requests`, `cryptography` promoted from transitive to direct.

## Decisions / gotchas

- **Gmail account selection is Google's account chooser** (`prompt=select_account`), plus an
  optional `loginHint`. One Google account with several channels produces one connection per
  channel; the UI shows the Gmail email so they can be told apart.
- **Scope note:** a channel-level revoke does not exist, so disconnect revokes the OAuth token at
  Google and deletes both documents.
- **Unverified-client caveat:** uploads stay private until the OAuth app passes YouTube's API
  audit. Expected; test on a throwaway channel.
- The resolved SRT lives in the publish document (Firestore 1 MB doc limit). Fine for a normal
  podcast-length video; a 2h+ transcript would need it moved to Cloud Storage.
- The metadata endpoints sometimes stretch the credentials' access token to ~2h.
- Publishing deletes only the Firestore record; the YouTube video is external and is not removed
  (documented in `contracts/firestore.md`).

## Verification

- `uv run ruff check .` clean; `uv run mypy app` clean (109 files).
- `bunx tsc --noEmit`, `bun run lint` (oxlint), `bun run lint:eslint` (1 pre-existing warning),
  `bun run build` all clean.
- Offline smoke test of PKCE, the local cipher round-trip, the authorization URL, and SRT/VTT
  builders.

## Not done / next step

- Set up the OAuth client (console), then run the Part 7b test flow. Nothing else is needed from
  the code side.
- Natural follow-ups: a channel video list (pull recent uploads), YouTube Analytics sync into
  BigQuery, and surfacing publish state in the websocket snapshot.
