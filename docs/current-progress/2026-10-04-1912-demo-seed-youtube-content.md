# Demo seed: CC-BY YouTube content + a UI seed button

## What I did

A fresh account has no published videos, so the creator-content features (style/RAG, transcripts,
thumbnail references) have nothing to learn from. Added a demo seed that loads a public **CC BY**
channel's content into the signed-in user's account.

**Seed data → GCS**
- `backend/scripts/upload_youtube_seed.py` compacts `fixtures/seed/youtube/<Channel>` into one JSON
  per channel (metadata + transcript text, thumbnails left as their public CDN URL) and uploads it
  to `seed/youtube/<slug>.json` in the **media bucket**. Reads the local (gitignored) dataset; the
  script is committed.
- Uploaded: `lawrencesystems` (60 videos, 58 transcripts, 471 KB), `psych2go` (60/59, 396 KB),
  `thehumanistreport` (60/56, 448 KB). `moxieboosted` skipped (no `index.jsonl` — not fully
  gathered). Provenance/licence: `fixtures/seed/youtube/ATTRIBUTION.md`.

**Backend**
- `services/seed_service.py`: `seed_youtube_content` reads the GCS JSON and writes a synthetic
  connection at `users/{uid}/connections/seed-<slug>` (`seedSource`/`seedLicense`/`seedAttribution`,
  a fresh `contentSyncedAt`) plus its `contentItems` (metadata + transcript). RAG picks it up via
  `primary_connection_id`.
- `api/seed.py`: `POST /api/seed/youtube-content` (authenticated). Body `{channel}` (default
  `lawrencesystems`).
- `ConnectionService.tokens_for_use` rejects a seed connection (`CONNECTION_IS_SEED`) so the sync
  buttons give a clear message instead of flipping it to `needs_reauth`.
- Config: `SEED_CONTENT_MAX_ITEMS` (default 60).

**Web**
- `lib/seed.ts` + a **"Load CC-BY demo"** button in the connections card header (Profile and the
  publish module). On success: "Loaded N videos from <channel> (CC BY) for the demo."

**Contracts**: OpenAPI path + schemas; `firestore.md` documents the seed connection.

## Verification

- `uv run ruff check .` clean; `uv run mypy app` clean (114 files).
- GCS objects readable via the app's storage client; payload well-formed (60 items, 6000-char
  transcripts).
- Route present in `app.openapi()`: `/api/seed/youtube-content`.
- `bunx tsc --noEmit`, `bun run lint`, `bun run lint:eslint` (0 errors), `bun run build` clean.

## Decisions / gotchas

- Thumbnails are **not** duplicated into GCS: they are public `i.ytimg.com` URLs the app already
  downloads (Phase 3). The seed JSON holds the metadata + transcripts, which is the data that
  matters for RAG.
- The seed is a **separate synthetic connection**, so it never mixes with a real channel's content
  and is removed by disconnecting it (or account delete). Sync endpoints reject it by design.
- CC BY requires credit; the result carries the attribution string (and `ATTRIBUTION.md` has the
  format) so the demo can show it.

## Not done / next step

- Surface the CC-BY attribution in the UI for seeded content.
- `moxieboosted` seed once its dataset is gathered.
- Phase 2c (comments) and the BigQuery mirror remain.
