# Phase 2: transcripts + YouTube Analytics into the creator context

## What I did

Extended the connector's read side and the creator-context pipeline so the writer sees the
creator's **own transcripts** and their **audience**, not just titles/descriptions.

**Connector**
- `connectors/base.py`: `ChannelVideo.has_captions`; new `CaptionTrack` and `AnalyticsReport`.
- `connectors/youtube.py`:
  - `list_captions(video_id)` and `download_caption(caption_id, tfmt)` (own videos only; requires
    edit permission, which we have via `youtube.force-ssl`).
  - `query_analytics(...)` builds a `youtubeAnalytics/v2` client and runs `reports.query` for the
    authenticated channel.
  - `_video_from` now reads `contentDetails.caption`.

**Service (`channel_content_service.py`)**
- `sync` now also pulls caption transcripts for up to `CHANNEL_TRANSCRIPT_MAX_VIDEOS` (default 10)
  videos that have captions and no stored transcript (re-syncs are then free). SRT/VTT is flattened
  to plain text and capped at `CHANNEL_TRANSCRIPT_MAX_CHARS` (default 6000). Stored as `transcript`
  + `transcriptLanguage` on the content item.
- `sync_audience` runs YouTube Analytics for the last `CHANNEL_ANALYTICS_DAYS` (default 28):
  channel summary (views, watch time, subs gained/lost, likes/comments/shares), viewer
  demographics (`ageGroup,gender`), traffic sources, top countries, and top videos. Stored as
  `audienceProfile` on the connection.
- `build_context` now attaches a transcript excerpt to each retrieved example and an `audience`
  block (summary + demographics + traffic) — all sent to the draft writer as `creatorContext`.

**API + web**
- `GET/POST /connections/{id}/audience[/sync]`.
- `web`: `syncConnectionAudience`/`getConnectionAudience`; a second (analytics) action on the
  connection card next to the "read content" sparkles button.

## Verification

- `uv run ruff check .` clean; `uv run mypy app` clean (112 files).
- Runtime: `_srt_to_text` flattens SRT; `_pick_caption_track` prefers manual-in-language →
  ASR-in-language → English → any.
- Routes present: `/api/connections/{connectionId}/audience` and `.../audience/sync`.
- `bunx tsc --noEmit`, `bun run lint`, `bun run lint:eslint` (0 errors), `bun run build` clean.

## Decisions / gotchas

- **Quota:** `captions.download` is 200 units + 50 to list. Capped at 10 videos/sync and skipped
  when a transcript already exists, so a re-sync is ~2 units. Analytics reports are ~1 unit each.
- **Auto-generated captions** may not download; creator-uploaded tracks do. Videos without any
  track are skipped (we cannot get their media to transcribe ourselves without breaking ToS).
- **Storage:** audience + transcripts live in Firestore for immediate app/RAG use. The design's
  BigQuery mirror (`creator_studio_social.*`) is **not** written yet — that needs the provisioned
  `social-sync` worker on the `social_sync` service account (the API SA has no BigQuery role).
- **Comments sentiment** is not implemented (Phase 2c) — lower RAG value than transcripts/analytics.

## Not done / next step

- Phase 2c: comments + sentiment summary.
- Phase 3: use the creator's `maxres` thumbnails as reference images in the thumbnail studio.
- BigQuery mirror via the social-sync worker (design intent).
- Consider embeddings for retrieval instead of the lexical ranker.
