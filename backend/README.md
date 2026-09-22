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
├── providers/       Provider interfaces (all Google SDK usage lives here)
├── services/        Firestore, Storage, Pub/Sub wrappers
├── agents/          ADK agents and reviewers
└── workers/         Pub/Sub handlers and Cloud Run jobs
```

## External services

Every external call goes through a provider in `app/providers/` and hits the real service:
Gemini Developer API for LLM calls (needs `GEMINI_API_KEY`), Speech-to-Text for
transcription, Cloud Storage and Firestore for data. Test uploads end to end with the sample
videos in `../fixtures/media/`.
