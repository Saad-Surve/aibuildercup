# AGENTS.md

Guidance for AI agents and engineers working in this repo. Start with `README.md` for what the
product does and what is implemented. For the design, see `docs/technical-design/README.md`.

## What this is

Resonance Creator Studio. A creator uploads one video and gets a timestamped transcript and a
multi-reviewer critique shown as a heatmap under the timeline. Findings link to the moment, an
explanation and a proposed edit. The same workspace uses the creator's earlier work for drafts,
thumbnails, localized captions and dubbing, a YouTube package, and scheduled publishing.

The repo and UI are named Resonance. The GCP project and some resource names are still
`habeas-codus`. This is a hackathon project: prefer a working demo over polish, and keep the
architecture clean.

## Repository map

| Path | What | Tooling |
|---|---|---|
| `web/` | Next.js 16 frontend | Bun |
| `backend/` | FastAPI API, workers, reviewers, providers | uv |
| `infra/` | Terraform for GCP resources (`infra/RESOURCES.md` is the inventory) | Terraform |
| `contracts/` | OpenAPI, Firestore and event contracts | - |
| `corpus/`, `fixtures/` | Localization corpus, sample media and import examples | - |
| `evals/` | Editorial benchmark sets (dev, held-out, long-form, real), interest model, retrieval cases; `evals/results/README.md` indexes every run | - |
| `docs/` | Architecture, costs, design, and the handoff in `docs/current-progress/HANDOFF.md` | - |

## Commands

```bash
# backend/
uv sync
cp .env.example .env
uv run uvicorn app.main:app --reload --port 8080
uv run ruff check .
uv run mypy app

# web/
bun install
cp .env.example .env.local
bun dev
bun run lint           # oxlint
bun run lint:eslint    # Next.js eslint config
bun run build
bun run format         # oxfmt

# infra/
terraform init
terraform plan         # review before every apply
```

## Rules

1. **Contracts first.** `contracts/openapi.yaml` is the API contract. If an endpoint changes,
   update the contract in the same change. Web and backend must not drift.
2. **Providers only.** Feature code never imports a Google SDK. Every external call goes through
   a provider in `backend/app/providers/`, using the interface in `base.py`.
3. **Real services, capped spend.** Development calls live GCP APIs. Sample media lives in
   `fixtures/media/`. Veo, Imagen and Gemini Pro are the expensive calls. Keep them behind the
   guards in `docs/costs.md`, and never call them in a loop or demo without a bound.
4. **Regions.** Use `us-central1`, except Speech-to-Text (Chirp 3), which uses the `us`
   multi-region. Do not use `us-east1`.
5. **Tooling.** `web/` uses Bun, `backend/` uses uv, `infra/` uses Terraform. Do not add npm,
   pip, poetry or yarn. Run `bun` only inside `web/`.
6. **No tests.** Do not add tests or testing libraries to web or backend. Delete any you find.
7. **Secrets** go in Secret Manager, never in git. `.env.local`, `.env` and `terraform.tfvars`
   are gitignored.
8. **Commit only when asked.** Run the verification commands before you report done.
9. **Handoff.** Read `docs/current-progress/HANDOFF.md` before starting. Update it in place when
   your change alters contracts, infra, deployed state, open decisions or verification gaps.
   Keep it current, not chronological. Do not create per-change notes.

## Building a feature

1. Find or add the endpoint and document shape in `contracts/openapi.yaml` and
   `contracts/firestore.md`.
2. Read the matching section in `docs/technical-design/`.
3. Backend: router in `app/api/`, logic in `app/services/`, external calls through a provider.
   Every user-owned read or write checks `ownerUid`.
4. Frontend: call the API only through `web/src/lib/api-client.ts`. Next.js 16 differs from
   older versions. Read the bundled docs described in `web/AGENTS.md` first.
5. Deletion: store project data under `users/{uid}/projects/{projectId}/...` in Firestore, or
   under `project_object_prefix(uid, projectId)` in Storage. Deleting a project
   (`ProjectService.delete`) removes both, and deleting an account (`UserService.delete_account`)
   removes the whole user tree. Anything stored outside those paths must be added to the delete
   path explicitly.
6. Run the verification commands above.

Provider usage looks like this:

```python
result = await providers.llm.complete_json(
    model=..., prompt_version=..., system=..., user=..., schema=...
)
```

## Gotchas

- Transcription starts from the GCS `object finalized` Pub/Sub push
  (`POST /api/internal/pubsub/video-events`). `POST /assets/{id}/complete` is the fast UX path.
  Both converge on one idempotent `transcribe` job.
- The Firebase default bucket (`habeas-codus.firebasestorage.app`) is not used. The app uses
  `habeas-codus-media`.
- Speech-to-Text long audio uses batch recognition. STT V2 cannot auto-detect AAC in MP4, MOV or
  M4A, so those files use an explicit decoding config.
- Firebase Terms of Service acceptance is console-only.
- Cloud Run runs one instance. Job locks and the realtime hub are process-local, so scaling out
  needs durable leases first.
- Deletion is real. Versioned buckets keep noncurrent generations until lifecycle expiry.
- Editorial eval sets are pre-registered. Tune only on `evals/editorial/` (dev). Never tune
  prompts against `evals/editorial-heldout/`, `editorial-longform/` or `editorial-real/`, or
  read their results while tuning; bump prompt versions when prompts change.
- A GCP budget is not a hard cap. The budget (8,500 INR, about $100) and the billing kill switch
  (`infra/budget.tf`) are a backstop, and billing data arrives with a delay.

## Where to look

| Question | File |
|---|---|
| Why was a decision made? | `docs/technical-design/README.md` |
| DB shape | `contracts/firestore.md`, `docs/technical-design/db-design.md` |
| API | `contracts/openapi.yaml`, `docs/technical-design/api-design.md` |
| Events | `contracts/events.md` |
| External calls | `backend/app/providers/`, `docs/technical-design/backend-plan.md` |
| GCP resources | `infra/RESOURCES.md` |
| Costs and guards | `docs/costs.md` |
| What has changed recently, and what is open | `docs/current-progress/HANDOFF.md` |
