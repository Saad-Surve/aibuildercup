# Resonance backend

FastAPI API, bounded Gemini reviewers, creator retrieval and media workers. The current
runtime uses Python async orchestration and Gemini function calling. Google ADK is an
installed dependency; no ADK Runner is used in the inspected request/worker paths.

[Architecture](../docs/architecture.md) · [API](../contracts/openapi.yaml) ·
[Firestore](../contracts/firestore.md) · [Cost model](../docs/costs.md)

## Run

Prerequisites: uv/Python 3.12+, Google Cloud access/ADC and FFmpeg with ffprobe.

```bash
gcloud auth application-default login
gcloud auth application-default set-quota-project habeas-codus
uv sync
cp .env.example .env
uv run uvicorn app.main:app --reload --port 8080
```

Local Swagger: `http://localhost:8080/docs`. API prefix: `/api`.
Development calls live services and can incur charges. Gemini uses ADC, not a Gemini API
key. `.env.example` is the local model configuration; `.env.deploy.example` records
production defaults. Confirm model availability at the configured endpoint before a run.
YouTube OAuth is optional for editing/reviewing; publishing requires a connected account.

## Layout

| Path | Responsibility |
|---|---|
| `app/api/`, `app/schemas/` | Authenticated routes, validation and typed response shapes |
| `app/providers/` | Gemini text/image/video/embeddings, STT, TTS, translation and public-source acquisition |
| `app/services/` | Ownership, persistence, workflow logic, retrieval and media helpers |
| `app/agents/` | Nine specialist reviewer prompts, normalization and bounded coordinator |
| `app/workers/` | Transcription, analysis, captions, dubbing, thumbnails, packaging and publication |
| `app/connectors/` | YouTube Data/Analytics adapter |
| `app/realtime/` | Project progress, subscriptions and process-local WebSocket hub |
| `app/assets/` | Caption fonts and bundled localization corpus |
| `scripts/` | Corpus collection/import/preset publication, user-content copying and quantitative benchmarks |

Synchronous cloud I/O runs off the event loop. Job IDs are atomically created; worker
execution locks are process-local. Keep the current one-instance deployment until durable
dispatch/leases and shared realtime delivery are implemented. There are no mock providers.

## Verify and evaluate

```bash
uv run ruff check .
uv run mypy app
uv run python scripts/estimate_cost.py
```

[Evaluation instructions](../evals/README.md) cover bounded live query embedding and
cached offline replay. No test suite/testing libraries are used in this repository.

[Creator import](../docs/creator-demo-import.md) and
[public corpus](../docs/creator-public-corpus.md) document collection, validation,
installation and deletion. Project outputs stay under project-owned paths; account-owned
library data stays under the user prefix. Secrets and local originals remain ignored.
