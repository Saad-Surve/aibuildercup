# Creator Helper Studio — Backend

FastAPI + Google ADK backend. See `../docs/technical-design/backend-plan.md`.

## Run

```bash
uv sync
cp .env.example .env
uv run uvicorn app.main:app --reload --port 8080
```

## Lint and types

```bash
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

Every external call goes through a provider in `app/providers/` and hits the real service.
LLM calls run on Gemini Enterprise Agent Platform (formerly Vertex AI), authenticated with
Application Default Credentials (locally `gcloud auth application-default login`; on Cloud Run
the runtime service account). There are two configs: `backend/.env.example` (local, cheap
`gemini-3.1-flash-lite`) and `backend/.env.deploy.example` (deployed, `gemini-3.8-flash`).
Speech-to-Text does transcription, and Cloud Storage and Firestore hold data. Test uploads end
to end with the sample videos in `../fixtures/media/`.

## Creator folder demo import

See [the import guide](../docs/creator-demo-import.md) for the local folder format and
`uv run python scripts/import_creator.py` validation/import/removal commands.
