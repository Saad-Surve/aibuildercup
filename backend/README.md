# Creator Helper Studio — Backend

FastAPI + Google ADK backend. See `../docs/technical-design/backend-plan.md`.

## Run

```bash
uv sync
cp .env.example .env
uv run uvicorn app.main:app --reload --port 8080
```

## Test / lint

```bash
uv run pytest
uv run ruff check .
uv run mypy app
```

## Layout

```
app/
├── main.py          FastAPI app, middleware, error envelope
├── config.py        Settings (pydantic-settings)
├── dependencies.py  Auth dependency
├── api/             Routers (health first, more to come)
├── auth/            Firebase Admin token verification
├── providers/       Provider interfaces + cassette record/replay
├── services/        Firestore, Storage, Pub/Sub wrappers
├── agents/          ADK agents and reviewers
└── workers/         Pub/Sub handlers and Cloud Run jobs
```

## Mock mode

`MOCK_MODE` controls every external call:

- `off` — always real
- `auto` — replay a cassette on hit, call real once and record on miss (default)
- `on` — cassette only, never network

Cassettes live in `../fixtures/cassettes`. See `../docs/technical-design/mock-and-seed.md`.
