# Medium / Substack / Reddit connectors (connect + cross-post)

## Research outcome (shaped the build)

- Reddit: healthy official OAuth2, free 100 QPM personal tier. Caveat: since
  late 2025 some new apps need manual Developer Support pre-approval.
- Medium: API deprecated, zero new tokens since Jan 2025. Legacy-token-only.
- Substack: no official write API; cookie-authenticated internal API works
  (draft/publish/schedule) but is fragile by nature.

## Backend

- `providers/medium.py` (me + create post, markdown, draft default),
  `providers/substack.py` (profile/draft/publish + minimal md→HTML, 1rps-safe
  single calls), `providers/reddit.py` (OAuth client + me + submit). All
  `requests`-based, `ConnectorError`-typed; feature code never touches HTTP.
- `schemas/connections.py`: platform enum ×4, `profileUrl`, connect + crosspost
  request/result schemas.
- `connection_service.py`: `connect_medium` (token→`/v1/me`), `connect_substack`
  (sid+subdomain→profile→publication), Reddit OAuth start/callback branch
  (permanent refresh, same state-doc pattern), platform-aware `sync` (re-verify
  → `needs_reauth`), revoke only for Google (Reddit has no revoke endpoint;
  bearer secrets die by deletion), `revoke_all` skips non-Google,
  `reddit_tokens_for_use` with Reddit refresh, raw `_load_secret` for
  token/cookie envelopes, `_save_tokens` platform param.
- New `services/crosspost_service.py` + `POST /projects/{id}/crossposts`
  (synchronous, nothing persisted): per-platform validation (title/body caps,
  subreddit default `u/{you}`, Substack schedule needs `scheduleAt`),
  `needs_reauth` mapping on 401s. Reddit submit via bearer-only client.
- `config.py` + `.env.example`: `REDDIT_OAUTH_*` (id/secret/redirect, default
  derived from `api_public_base_url`).
- Contracts: `openapi.yaml` (platform enum, profileUrl, connect + crosspost
  paths/schemas, OAuth enums widened), `firestore.md` (platforms, secret
  envelopes, revoke note).

## Web

- `lib/types.ts` + `lib/connections.ts`: platforms, profileUrl, crosspost
  client fns. `calendar/platform.tsx`: medium/substack/reddit logo mapping
  (+ new official `public/reddit.svg` from Simple Icons, brand orange).
- `text-platform-connections.tsx` (new): per-platform cards with real connect
  flows (token dialog / cookie+subdomain dialog / Reddit OAuth with
  `?reddit=` callback handling mirroring the YouTube pattern), status badges,
  disconnect. Mounted in `account-connections.tsx` as "Writing platforms".
- `draft/crosspost-card.tsx` (new): platform tabs, account picker, title/body
  prefilled from the draft cache, per-platform options (Medium visibility,
  Substack mode/audience/send/schedule, Reddit subreddit/link), result link.
  Mounted in `DraftWorkspace` under the header.

## Docs

- `docs/connectors/text-platforms-setup.md`: step-by-step for all three
  (Medium token location + dead-end warning, Substack devtools cookie steps,
  Reddit app creation with exact redirect URIs + pre-approval caveat + profile
  vs subreddit guidance), plus the draft posting flow.

## Verification / gotchas

- `ruff` + `mypy` (132 files) clean; `bun lint`/`eslint` 0 errors; `build` clean.
- Reload saga again: `--reload` fired mid-edit and served partial code
  (openapi lacked crossposts); killed `:8080` and restarted fresh — live spec
  now shows all paths + 4-platform enum. Lesson stands: verify `/openapi.json`
  after multi-file backend edits, don't trust the reloader.
- No live-auth test (needs the user's real Medium token / Substack cookie /
  Reddit app). First live pass: connect all three from Settings, then post a
  draft to each.
- Cost: all free-tier/personal; no paid calls, no new infra.

## Not done / next step

- Live credential pass above; Substack `send:true` is irreversible — UI already
  defaults to draft mode and labels the risk.
- Optional later: scheduled crossposts via jobs, content read-back for style
  signals, Reddit pre-approval fallback copy in the UI.
