# YouTube connector audit + media-connector research

## What I did

Audited the existing YouTube connector end to end (no code changes) and researched other
publish/analytics platforms we could add. Findings below; this is the handoff for whoever picks
up connector work next.

## Current state of the YouTube connector (it is real and works)

Code map:

- `backend/app/connectors/base.py` — `SocialConnector` protocol (`list_channels`,
  `refresh_channel`, `revoke`), `ConnectorError`, `ChannelInfo`, `UploadedVideo`.
- `backend/app/connectors/youtube.py` — `channels.list`, resumable `videos.insert` with progress,
  `thumbnails.set`, `captions.insert`, error normalisation.
- `backend/app/services/oauth_service.py` — Google auth-code + PKCE, refresh, revoke, userinfo.
- `backend/app/services/connection_service.py` — one connection per channel, encrypted tokens,
  refresh-in-place, `needs_reauth`, `sync` (channel stats only), revoke+delete.
- `backend/app/services/token_cipher.py` — KMS in prod, passphrase Fernet locally.
- `backend/app/services/publish_service.py` + `workers/publish_worker.py` — freeze video/thumb/
  captions, resumable upload, idempotent worker.
- API `connections.py`, `publishes.py`; web `youtube-connections.tsx`, `publishing-module.tsx`.

What works: connect a Google account (account chooser), one connection per channel, encrypted
token storage/refresh, channel-stats sync, and full project → YouTube publish (video + thumbnail +
captions) with progress and retry.

## What is still needed

**To finish YouTube (small):**

1. Console setup only: create the Web OAuth client, register the callback, add scopes, test
   users; store id/secret in Secret Manager. Documented in `LOCAL_SETUP.md` Part 7b.
2. Unaudited-client caveat: uploads stay private until the OAuth app passes YouTube's API audit.
3. Quota comment in `youtube.py` is stale. Current (2026) YouTube model: `videos.insert` has its
   own bucket of **100 uploads/day** (cost 1 each), and 10,000 units/day for everything else
   (`captions.insert` = 400 units). The "~1600 units" note should be corrected.
4. Staging risk: `publish_max_source_bytes` is 8 GB but the worker downloads the whole file to
   Cloud Run's temp disk. Default Cloud Run disk is ~2 GB, so large uploads fail regardless of the
   config cap. Either raise the instance disk or stream/upload via `PULL_FROM_URL`/signed URL.

**Bigger gaps in the connector surface:**

5. `sync` only refreshes channel stats. The design (`api-design.md` §connections, `diagrams.md` §3)
   describes an async analytics/comment sync that loads BigQuery and runs sentiment. The infra is
   fully provisioned but unused:
   - BigQuery datasets/tables exist (`creator_studio_social` posts/metrics/comments/
     audience_aggregates; `creator_studio_ai` comment_sentiment) — `infra/bigquery.tf`.
   - `social-sync-events` topic + subscription + `social-sync` service account exist —
     `infra/pubsub.tf`, `infra/service_accounts.tf`, `infra/iam.tf`.
   - `JobType.sync_social` and `events.py` topic mappings for `social.sync.requested/completed`
     exist, but **nothing publishes or consumes them**. There is no sync worker, no BigQuery
     loader, no raw-social bucket writer.
   - No YouTube video list (`playlistItems.list`), no comments (`commentThreads.list`), no YouTube
     Analytics API usage despite `yt-analytics.readonly` being requested.
6. `ConnectionPlatform` enum and the OpenAPI `platform` enum are **youtube-only**; `Publish.platform`
   and `_DISPLAY_SCOPES` are YouTube-shaped. Adding a platform needs these widened.
7. OAuth is Google-specific (`GoogleOAuthClient`, hard-coded endpoints). Other platforms need their
   own OAuth client; the state document already carries a `platform` field, so the seam is close.
8. Account deletion does **not** revoke OAuth tokens at Google: `UserService.delete_account` deletes
   the Firestore tree + storage prefix only. `ConnectionService.delete` revokes, but account delete
   bypasses it. Add a revoke-all-connections step before the tree delete.
9. The `SocialConnector` protocol does not include upload methods (`upload_video`,
   `set_thumbnail`, `upload_caption` live only on `YouTubeConnector`). The publish worker is typed
   to the concrete `YouTubeConnector`. Generalising the seam means adding an upload/post interface.
10. No webhook/poll for YouTube processing completion; `publishing` stays until we mark it. Fine for
    the demo, not accurate.
11. Caption SRT is stored inline in the publish Firestore doc (1 MB limit) — fine for podcast length,
    not for very long transcripts.
12. No connections/audience UI: the sidebar has no Connections entry and `Audience insights` is
    `ready: false`; there is no `/connections` route (only `/profile` hosts the card). DESIGN.md
    describes `ConnectionsPage`, `SyncHistoryTable`, `AudienceInsightsPage` that do not exist.

## Research: other media connectors

Ranked for a creator studio that needs both **publish** and **analytics/comments**, under a
hackathon budget. "Auth" = how hard onboarding/approval is.

| Platform | Publish | Analytics/comments | Auth / approval | Notes |
|---|---|---|---|---|
| **TikTok** (Content Posting API) | Direct Post `video.publish`, photo posts | Research/Display API separate | App review; unaudited = SELF_ONLY + 5 users/day | Same audit pattern as YouTube. Good short-form fit. |
| **Instagram** (Graph API) | Reels/feed via `/<ig>/media` + `media_publish` | Insights, comments | IG professional account + Facebook Login; app review for public | Video is async: poll container `status_code` until FINISHED. 50–100 posts/24h. |
| **Facebook Pages** (Video/Reels API) | Reels + videos via resumable upload | Page insights, comments | Page token + `pages_manage_posts`; app review | Reels only to Pages, 30/24h, 3–90s. |
| **Threads** (Meta) | Text/IMAGE/VIDEO/carousel | Insights, replies | Separate Meta app (Threads use case) + tester invite | 250 posts/24h; two-step container→publish; 60-day long-lived token. |
| **LinkedIn** (Posts + Videos API) | Video/image/text to member or org | `r_organization_social` for comments; `r_member_social` restricted | `w_member_social` easy; org needs admin role; `r_member_social` approval-only | Clean initializeUpload → URN → post flow. Good for the "professional" artifact. |
| **X** (API v2) | Post text/image/video | Owned reads `$0.001`; public reads `$0.005` | Pay-per-use, **no free tier** | Posting $0.015 ($0.20 if it contains a URL). Cheap for demo volume, pricey at scale. |
| **Pinterest** (v5) | Image + video pins | Pin analytics (lifetime metrics) | OAuth `pins:write`; sandbox support | Video pin = register media → upload → poll → create pin. |
| **Bluesky** (AT Protocol) | Text/image/video via `com.atproto.repo.createRecord` | Public firehose/reads | **No app review, no API key** — app password/OAuth | Easiest by far; great for a live demo. Video goes via `video.bsky.app` job polling. |
| **Mastodon** | `POST /api/v1/statuses` + media upload | Public timelines/statuses | Open; OAuth per instance | Trivial text/image; video attach; no central app review. |
| **Vimeo** (API 3.4) | Resumable (tus)/form/pull upload | Stats scope, comments | App + **upload access request**; free tier needs approval ticket | Long-form hosting alternative to YouTube; 300 GB/24h. |
| **Twitch** (Helix) | **No upload** — clips/VODs only | Videos, clips, streams | OAuth app | Read/clip only; good for clip analytics, not publishing. |
| **Snapchat** (Marketing API) | Public Profile API is **partner-gated**; Ads API open | Ads reporting; profile metrics | Ads API open to all; organic publish is partner-only | Not a realistic self-serve publish connector for the hackathon. |
| **Podcast / audio** (Spotify, Apple, Amazon) | **No upload API** — RSS feed is the connector | Spotify for Creators analytics (limited) | None | Generate a Podcast RSS feed from the transcript/audio; directories pull it. Cheap, high-leverage, no OAuth. |
| **Rumble** | Partner Upload API (email `bd@rumble.com` for a 40-char token) or browser automation | oEmbed read only | Invite/approval-only | Not self-serve; skip. |

**Aggregators (skip building each platform):** Ayrshare (13 networks, API-first, ~$149/mo/profile),
Postiz (open-source/self-host, 30+ channels), Mixpost (self-host, MIT/paid Pro), Blotato
($29/mo flat, hosted MCP), Zernio. These collapse N OAuth integrations into one API and are a
legitimate shortcut if breadth matters more than depth. Trade-off: they own the OAuth and the raw
data, which conflicts with our BigQuery/analytics design.

### Recommendation for this project

- **Do next (cheap, high demo value):** Bluesky + Mastodon. Open APIs, no review, video support,
  so we can show "one project → many platforms" without waiting on audits. Also add a **Podcast
  RSS** output (no OAuth) since the app already has audio/dubbing.
- **Do next (strategic):** finish the **social sync worker** (YouTube `playlistItems` + comments +
  YouTube Analytics → raw-social GCS → BigQuery → sentiment). All infra already exists; this makes
  the "Audience insights" tab real and reuses the existing connector seam.
- **Later (best fit after YouTube):** TikTok (short-form, same audit model) and Instagram Reels
  (both are where the generated shorts would actually go). Meta app + Threads share one review.
- **Avoid for the demo:** X (pay-per-use, no free tier), Snapchat (partner-gated organic publish),
  Rumble (invite-only), Twitch (no upload).

### Self-hosted aggregators (deep dive: Postiz vs Mixpost)

The important myth to kill first: **self-hosting an aggregator does not remove the platform app
review.** You still register your own developer app on each platform (Meta, YouTube, TikTok) and
go through their approval — you just own the OAuth instead of the vendor. The aggregator only
saves you from writing N connector clients and N token-refresh loops.

**Postiz** (`gitroomhq/postiz-app`, ~36k stars, AGPL-3.0, TS/Next.js/NestJS)
- 3 app services (frontend/backend/orchestrator) + Postgres + Redis + **Temporal** + storage.
  Reference compose runs ~9 containers; heavy footprint. Tested on a 2 GB / 2 vCPU VM.
- Install: Docker Compose, Docker, **Helm** (so GKE-ready), Coolify, Railway.
- Public API served identically by cloud and self-host at `https://{your-domain}/api/public/v1`,
  API-key auth. Endpoints: list channels/integrations, get OAuth connect URL, upload media,
  create/schedule/draft/delete posts, webhooks on publish. Per-platform settings via `__type`.
- 30–34 channels including Bluesky, Mastodon, Nostr, Farcaster — plus an MCP server and CLI.
- License: AGPL-3.0. Running it as a **separate service and calling its public API is fine**;
  forking/linking its code into our app triggers the copyleft (we'd have to release our changes).

**Mixpost** (`inovector/mixpost`, ~3.7k stars, Laravel/PHP + Vue)
- Stack: Laravel + MySQL/Postgres/SQLite + Redis + Horizon queue; much lighter than Postiz, no
  Temporal. Install as Docker, a standalone app, or a Composer package inside an existing Laravel app.
- Editions: **Lite (MIT, free)** — basic publishing, historically Twitter/Facebook only and **no
  API**; **Pro (one-time $299, proprietary)** — ~11–12 channels (incl. YouTube, TikTok, IG, Threads,
  Bluesky, Mastodon, Pinterest, Google Business) and the built-in REST API. Enterprise adds admin.
- API (Pro/Enterprise) at `https://{host}/{corePath}/api/{workspaceUuid}/...`, Bearer token, token
  hashed and shown once; OpenAPI spec available. Posts are always created as draft then promoted to
  scheduled; media uploaded first and referenced by id.
- Last commit ~7 months ago vs Postiz's hours — Postiz is far more actively developed.

Other open-source options (not recommended): **Socioboard** (old PHP, largely abandoned),
**Shoutify** (archived/read-only), **OpenSMM** (early, FB Pages only), **Postely** (runs on-device,
not a server), **Bulkit.dev** (niche).

**GCP deployment reality (for either):**
- Both need always-on processes (Temporal orchestrator / Horizon workers) and persistent
  Postgres + Redis. Cloud Run alone is a poor fit for the stateful parts.
- Cheapest path: one Compute Engine VM (e2-small/medium, ~$13–25/mo) running Docker Compose with
  local Postgres/Redis. Cleaner path: GKE (Helm) + Cloud SQL + Memorystore, but Cloud SQL and
  Memorystore have **no free tier** (~$45+/mo before compute).
- Postiz now stores media on the local filesystem by default; on GCP you'd mount a GCS bucket
  (gcsfuse) or keep it on the VM. Mixpost uses Laravel's disk abstraction (GCS driver possible).
- Budget: this is a second stack with its own datastore and auth, against a ~$100 budget and a
  billing kill switch. Non-trivial.

**Fit with our architecture — the hard parts:**
- **Multi-tenancy.** Our users authenticate with Firebase; the aggregator has its own users,
  workspaces and API keys. Neither tool is an embeddable multi-tenant OAuth broker out of the box.
  You'd either (a) single-tenant — connect the studio's own channels once (easy, good for a demo),
  or (b) map each creator to an aggregator workspace/customer and mint per-user keys (real work,
  and Postiz's customer model is thin).
- **Data ownership.** The aggregator holds the OAuth tokens and normalised analytics, which
  conflicts with our BigQuery audience-insights design — we'd pull from the aggregator API instead
  of the platform, and their analytics coverage is shallower than the platform APIs.
- **Integration seam.** Either way it slots in behind our connector provider seam as one adapter
  (upload media → create post → webhook back), which is less code than N native connectors — but it
  adds a service to run, not just an API to call.

**Verdict:** for the hackathon, don't self-host an aggregator. Either implement the 2–3 easiest
native connectors (Bluesky/Mastodon) directly, or use a *hosted* aggregator (Ayrshare/Blotato)
behind the seam. If self-hosting is a hard requirement, **Postiz** is the better fit (API parity,
webhooks, Helm, active, TS stack closer to our web) but is AGPL + ~9 containers; **Mixpost** is
lighter and MIT at the Lite tier, but the API is Pro-only and channel breadth is narrower.

## Decisions / gotchas

- The connector seam is half-abstracted: the read protocol exists, but uploads are YouTube-only and
  the worker is typed to `YouTubeConnector`. Widening `SocialConnector` is the prerequisite for any
  second platform.
- The entire social-analytics pipeline (BigQuery tables, Pub/Sub topic/sub, service account,
  `JobType.sync_social`, event mappings) is scaffolded and **unused**. Cheap win.
- Account deletion leaks OAuth grants at the provider (no revoke) — a correctness/privacy gap.
- Unaudited clients on both YouTube and TikTok force private/self-only uploads; budget for the
  audit if the demo must show public posts.

## Not done / next step

- No code changed. Next step is a decision on ordering; then widen `SocialConnector` +
  `ConnectionPlatform`, or stand up the sync worker first (the latter needs no new platform).
