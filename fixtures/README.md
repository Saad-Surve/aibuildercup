# Fixtures

Deterministic data used for development so nobody burns AI credits or needs real platform
accounts. Full design in `../docs/technical-design/mock-and-seed.md`.

```text
fixtures/
├── cassettes/    recorded provider responses, keyed by request hash
└── seed/         demo users, projects, transcripts, analyses, artifacts
```

## Cassettes

One JSON file per recorded provider response. Written by the backend when `MOCK_MODE=auto`
misses, replayed when it hits. Commit them after review.

Do not put secrets, user tokens, or private video content in a cassette.

## Seed

The backend seed script (`backend/scripts/seed.py --demo`) writes this shape into Firestore,
Cloud Storage, and BigQuery so the UI always renders a full workspace.
