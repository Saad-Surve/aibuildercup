# Phase 3: creator thumbnails as image-model style references

## What I did

The thumbnail studio now passes a few of the creator's **already-published thumbnails** to the
image model as style references, alongside the source-video frames, so generated concepts match
their established visual style.

- `channel_content_service.py`: `creator_thumbnail_references(owner_uid, limit)` — resolves the
  user's most recently synced channel, reads the stored `thumbnailUrl` for up to `limit` videos,
  downloads them (public `i.ytimg.com`, best-effort, 5 MB cap), and returns them as `MediaPart`s
  labelled "a past thumbnail from this creator's channel — match its style, do not copy".
  Helpers `_download_image` / `_image_mime`.
- `thumbnail_worker.py`: `_generate_batch` fetches the creator references once per batch and appends
  them to each concept's frame references. `_build_generate_prompt` now takes `has_frames` and
  `has_creator_references` separately: frames → "preserve the presenter's face"; creator thumbnails
  → "match the style, do not copy". `build_worker_services` / `live_worker_dependencies` build a
  `ChannelContentService`.
- Config: `THUMBNAIL_CREATOR_REFERENCES` (default 3).

## Verification

- `uv run ruff check .` clean; `uv run mypy app` clean (112 files).
- `_image_mime` / `_download_image` behave (jpg/png detection; a bad URL returns None).

## Decisions / gotchas

- Fully automatic: if the user has synced channel content, thumbnails get style references; if not,
  behaviour is unchanged. No API/UI change (the existing generate request is untouched).
- The references are the **1280×720 maxres** thumbnail (the highest YouTube exposes); not the
  original upload. Good enough for style.
- Best-effort throughout: a failed download or a missing sync never fails a thumbnail batch.

## Not done / next step

- Phase 2c (comments + sentiment) still not implemented.
- BigQuery mirror via the provisioned social-sync worker.
- Optional: an opt-out toggle for style references, and a content/audience profile UI.
