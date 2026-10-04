# Fix: hide sync actions on seed connections (the "couldn't load" investigation)

## What the user hit

Clicked "Load CC-BY demo". Investigation: the seed **succeeded** — Cloud Run logs show
`POST /api/seed/youtube-content` → `200 OK` twice (13:50, 14:12), creating
`users/{uid}/connections/seed-lawrencesystems`. The two `400`s that followed are the **sync buttons
on the seeded connection** (`/content/sync`, `/audience/sync` → `CONNECTION_IS_SEED`), which is
expected — a seed connection has no OAuth tokens.

So the seed pipeline works. The "page couldn't load" is client-side and not reproduced from the
API side; the leading hypothesis is a **stale JS chunk** after the many deploys (hard refresh).

## What I changed

- `Connection` schema (+ OpenAPI, web type) now exposes `isSeed` (true when the doc has
  `seedSource`).
- `youtube-connections.tsx`: a seed connection shows a **"CC-BY demo"** badge and **hides the
  sync buttons** (read content / analytics / refresh) — they would 400 — keeping only Disconnect.
  This removes the confusing failures.

## Verification

- `uv run ruff check .` clean; `uv run mypy app` clean (114 files).
- `bunx tsc --noEmit`, `bun run lint`, `bun run build` clean.

## Gotchas

- A seed connection is intentionally not syncable; disconnect removes all its seeded data.
- The seeded content is what the RAG/draft features use (most recently synced connection wins).

## Not done / next step

- If the "page couldn't load" persists after a hard refresh, need the exact browser console error
  and URL to diagnose further.
- CC-BY attribution line in the UI still pending.
