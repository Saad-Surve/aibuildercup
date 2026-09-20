# Habeas Codus — Creator Helper Studio

AI studio that reviews a creator's video, explains what works and what does not, and generates
derivative content. Hackathon project.

## Repository layout

| Path | Owner | What |
|---|---|---|
| `web/` | Engineer A | Next.js frontend (Bun) |
| `backend/` | Engineer B | FastAPI + Google ADK API and workers (uv) |
| `infra/` | Engineer C | Terraform for all GCP resources |
| `contracts/` | shared | Frozen API, event, and Firestore contracts |
| `fixtures/` | shared | Cassettes and seed data for offline development |
| `corpus/` | Engineer C | Localization glossaries and trap list |
| `docs/` | shared | Technical design |

## Quick start

### Backend

```bash
cd backend
uv sync
cp .env.example .env
uv run uvicorn app.main:app --reload --port 8080
```

### Web

```bash
cd web
bun install
cp .env.example .env.local
bun dev
```

Open http://localhost:3000.

### Infra

```bash
cd infra
terraform init
terraform plan
```

## Design

Start with `docs/technical-design/README.md`. The three-engineer split is in
`docs/technical-design/workstreams.md`.

## Development without spending money

Every external call goes through a provider with a cassette implementation. `MOCK_MODE=auto`
(default) replays recorded responses and only calls the real service on a miss. See
`docs/technical-design/mock-and-seed.md`.

## GCP project

`habeas-codus`, region `us-central1`. Resource inventory is in `infra/RESOURCES.md`.
