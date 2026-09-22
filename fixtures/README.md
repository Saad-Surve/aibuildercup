# Fixtures

## Media

`fixtures/media/` holds sample videos for testing uploads end to end. They are kept in git so
anyone can exercise the upload → transcription pipeline without hunting for a file. Do not
delete them.

## Seed

`fixtures/seed/` is reserved for the demo seed bundle (`backend/scripts/seed.py --demo`, not
built yet). The seed reads the same JSON shapes the API returns, so the frontend cannot tell
the difference between seeded and live data.
