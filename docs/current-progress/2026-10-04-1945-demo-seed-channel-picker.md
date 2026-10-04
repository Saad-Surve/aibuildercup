# Demo seed: pick a channel (default Psych2Go)

## What I did

Lawrence Systems is expert-level tech; for a demo that is hard for a general audience to judge. The
local seed already has a far more accessible CC-BY channel, so the seed button now lets you choose.

- **Psych2Go** (431 CC-BY videos: psychology, mental health, relationships — e.g. "15 Styles of
  Distorted Thinking", "Post-traumatic Stress Disorder + How To Cope") — already gathered and
  uploaded (`seed/youtube/psych2go.json`, 60 videos, 59 transcripts).
- **Lawrence Systems** (tech/self-hosting, expert).
- **The Humanist Report** (politics/commentary).

Changes:
- `youtube-connections.tsx`: the "Load CC-BY demo" button is now a **dropdown** with the three
  channels (friendly labels + a hint); picking one seeds it.
- Default seed channel is now `psych2go` (web `lib/seed.ts`, backend
  `SeedYouTubeContentRequest`, `SeedService`, OpenAPI default).

## Verification

- `uv run ruff check .` clean; `uv run mypy app` clean (114 files).
- `bunx tsc --noEmit`, `bun run lint`, `bun run lint:eslint` (0 errors), `bun run build` clean.

## Decisions / gotchas

- CC-BY channels are rare outside the PleIAs/YouTube-Commons dataset (721k channels, 2M+ videos);
  the seed picked 4 from one slice. Adding a new channel needs its `catalog.txt` + a `gather.py`
  run (yt-dlp), not just a name.
- Psych2Go content is animated and presenter-less, so thumbnail style references will be illustrated
  rather than photographic — worth knowing for the thumbnail demo.

## Not done / next step

- Re-run the seed to test Psych2Go end-to-end.
- CC-BY attribution line for seeded channels still pending.
