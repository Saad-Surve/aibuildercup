# Phase 1: read back channel content + RAG into draft generation

## What I did

Wired the YouTube connector's read side so the studio learns from the creator's **already-published
videos**, then fed the most relevant ones into draft generation as style evidence (RAG).

**Connector (read-back)**
- `connectors/base.py`: new `ChannelVideo` dataclass; `SocialConnector` gains `list_videos`.
- `connectors/youtube.py`: `list_videos(uploads_playlist_id, max_videos)` — `playlistItems.list`
  (1 unit/page of 50) for ids, then `videos.list` (1 unit/50) for
  snippet/contentDetails/statistics/status. Parses title, description, tags, publishedAt, duration,
  view/like/comment counts, best thumbnail URL, `hasCustomThumbnail`, language. No `search.list`.

**Persistence + profile**
- New `services/channel_content_service.py`: `sync` reads the channel's videos into
  `users/{uid}/connections/{id}/contentItems/{videoId}`, then builds an aggregate
  `ContentStyleSummary` (avg title words, % titles with a number/emoji, description length/hashtag
  use, upload cadence, common title openers, top tags). `profile` returns summary + top/recent
  items. `build_context` / `build_context_for_user` do lexical retrieval (light stemming, title
  weighted > tags > description) to pick the k most query-relevant past videos.
- `ConnectionService` now persists `uploadsPlaylistId` on the connection and exposes
  `contentSyncedAt` / `contentItemCount`. `Connection` schema + OpenAPI updated.
- Paths: `content_items_collection_path`, `content_item_path` (under the connection, so the
  recursive account delete covers it).

**RAG into draft generation**
- `DraftService` takes an optional `ChannelContentService`; `_generate_blocks` now sends
  `creatorContext` (style summary + top-k similar past titles/descriptions) alongside the brief, and
  `GENERATE_SYSTEM` tells the writer to match the creator's established voice using that evidence.
  Uses the user's most recently synced connection; absent when nothing is synced.

**API + web**
- `POST /api/connections/{id}/content/sync`, `GET /api/connections/{id}/content`.
- `web`: `connections.ts` gets `syncConnectionContent`/`getConnectionContent`; the connection card
  gets a "Read channel content" (sparkles) button and shows "N videos read".

**Config**
- `CHANNEL_CONTENT_MAX_VIDEOS` (default 50).

## Verification

- `uv run ruff check .` clean; `uv run mypy app` clean (112 files).
- Runtime check: `build_style_summary` and `retrieve_examples` behave (stemming folds
  invest/invested/investing; `save money` ranks the money videos).
- Routes present in `app.openapi()`: `/api/connections/{connectionId}/content` and `.../content/sync`.
- `bunx tsc --noEmit`, `bun run lint` (oxlint), `bun run lint:eslint` (0 errors), `bun run build` clean.

## Decisions / gotchas

- Quota: listing 50 videos is ~2 units; no `search.list` (100). Transcripts (captions.download,
  200 units) are deliberately **not** fetched in Phase 1 — that is Phase 2.
- Retrieval is lexical (no embeddings) for now; light suffix stripping keeps it useful without a
  new provider. Embeddings/Vertex are a later upgrade.
- `list_items` orders by `publishedAt` (a Firestore timestamp), single-field index (auto).
- RAG picks the user's most recently synced channel; multi-channel selection is a later refinement.

## Not done / next step

- Phase 2: captions (own-video transcripts, capped), comments, and YouTube Analytics
  (demographics/traffic/retention) into the provisioned BigQuery tables.
- Phase 3: thumbnails as image references for the thumbnail studio.
- Consider embeddings for retrieval, and a content-profile UI (top videos, style stats).
