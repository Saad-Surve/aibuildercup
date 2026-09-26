# AGENTS.md

Guidance for any AI agent (or new engineer) working in this repository. Read this first, then
`docs/technical-design/README.md`.

## 1. What this project is

**Habeas Codus — Creator Helper Studio.** An AI studio where a creator uploads one video and gets:

1. A timestamped transcript.
2. A multi-reviewer critique shown as a **heatmap under a timeline** (truth, clarity, structure,
   legal/safety, cultural/localization, platform fit, and more). This is the flagship feature.
3. Derivative content: short-form clips, thumbnails, social posts, blogs, localized captions and
   dubbing.
4. A project-scoped chat agent that can talk about anything in the project.

It is a hackathon project. Optimize for a winnable demo, not enterprise polish. But keep the
architecture clean, because the design already is.

Full design: `docs/technical-design/`. Current state: `docs/current-progress/`.

## Session protocol (read this first)

**On start:** read the most recent file in `docs/current-progress/`. It tells you what already
exists, what was decided, and what the next step is. Do this before touching anything.

**On finish:** write a new timestamped file in `docs/current-progress/` named
`YYYY-MM-DD-HHMM-<short-slug>.md`. Record:

- What you did.
- What changed structurally (contracts, schema, infra).
- Anything you decided or discovered (gotchas).
- What is not done and what the next step is.

Do this after every meaningful unit of work, not only at the end of a long session. The progress
folder is the handoff log between people and agents. If you changed something and did not write a
note, the next agent starts blind.

## 2. Non-negotiable rules

1. **Contracts first.** `contracts/openapi.yaml` is the frozen API contract. If you change an
   endpoint, update it. The web client is generated from it. Do not let web and backend drift.
2. **Never import a Google SDK directly in feature code.** Every external call goes through a
   provider in `backend/app/providers/`. Feature code never touches a Google SDK directly.
3. **Use real services.** Development calls the live GCP APIs (Gemini on Agent Platform /
   Vertex AI, Speech-to-Text, Storage, Firestore). Test uploads with the videos in
   `fixtures/media/`. Keep paid calls (Veo, Imagen, Gemini Pro) capped.
4. **Region is `us-central1`, except Speech-to-Text which uses the `us` multi-region** (Chirp 3
   is GA there). Do not use `us-east1` (Speech-to-Text is not GA there).
5. **Tooling:** `web/` uses **Bun**. `backend/` uses **uv**. `infra/` uses **Terraform**.
   Do not introduce npm, pip, poetry, or yarn.
6. **Never commit secrets.** `.env.local` and `terraform.tfvars` are gitignored. Secrets belong in
   Secret Manager.
7. **Do not commit unless the user asks.** Run the verification commands first.
8. **Read the latest `docs/current-progress/` note before starting, and write a new one before you
   stop.** See the session protocol above. No exceptions.

## 3. Repository map

| Path | What | Tooling |
|---|---|---|
| `web/` | Next.js frontend | Bun |
| `backend/` | FastAPI API + workers + agents | uv |
| `infra/` | Terraform for all GCP resources | Terraform |
| `contracts/` | OpenAPI, event, Firestore contracts | — |
| `fixtures/` | Sample media + seed data | — |
| `corpus/` | Localization glossaries + trap list | — |
| `docs/technical-design/` | The design | — |
| `docs/current-progress/` | Timestamped progress notes | — |

## 4. Commands

### Backend (`backend/`)

```bash
uv sync
cp .env.example .env
uv run uvicorn app.main:app --reload --port 8080

uv run pytest          # tests
uv run ruff check .    # lint
uv run mypy app        # types
```

### Web (`web/`)

```bash
bun install
cp .env.example .env.local
bun dev

bun run build          # build
bun run lint           # lint (oxlint)
bun run lint:eslint    # lint with the Next.js eslint config
bun run format         # format (oxfmt)
```

### Infra (`infra/`)

```bash
terraform init
terraform plan
terraform apply
```

## 5. GCP facts

- Project: `habeas-codus`. Region: `us-central1` (except Speech-to-Text, which uses the `us`
  multi-region because Chirp 3 is GA there).
- Full resource inventory: `infra/RESOURCES.md`.
- Firebase web config is in `infra/RESOURCES.md` (public, safe to expose).
- **Cost safety:** there is a budget (~$100) and a kill switch Cloud Function that detaches billing
  when spend hits it. Development uses free-tier APIs (Gemini flash, Speech-to-Text) so it should
  never come close. Do not add services that call paid APIs on a loop without a cap.
- The most expensive calls are Veo (~$0.15–0.40/sec), Imagen, and Gemini Pro. Keep them behind the
  cost cap; never call them in a dev loop or demo without a bound.

## 6. How to build a component (the workflow)

When someone asks you to build something, do this:

1. **Find the contract.** Check `contracts/openapi.yaml` and `contracts/firestore.md` for the
   endpoint/document shape. If it does not exist, add it there first.
2. **Read the relevant design section** in `docs/technical-design/` (e.g. `backend-plan.md`,
   `frontend-plan.md`).
3. **Backend:** add the router in `app/api/`, the logic in `app/services/`, and use a provider for
   any external call. Persist via a service, not inline. Every user-owned read/write must check
   `ownerUid`.
4. **Frontend:** consume the API through `src/lib/api-client.ts`. Follow the patterns in `web/` —
   read `web/node_modules/next/dist/docs/` first, this Next.js version differs from older ones.
5. **Add tests.** Backend: pure logic (aggregation, path builders, idempotency, normalization)
   must be unit tested. Add a provider in `app/providers/` when the feature calls an external
   service; feature code never imports a Google SDK directly.
6. **Wire the delete pathway.** Every new feature must think about deletion. Project data is
   deleted by Firestore recursive tree + Cloud Storage prefix, so store new project-scoped data
   under `users/{uid}/projects/{projectId}/...` (Firestore) or the matching object prefix
   (`project_object_prefix`) and it is covered automatically. Anything stored *outside* those
   paths (a top-level collection, a different bucket, a third-party record) must be added to the
   delete path explicitly, with a test. `ProjectService.delete` / `UserService.delete_account`
   are the reference implementations.
7. **Verify** with the commands in section 4. Do not claim done without running them.
8. **Update** `contracts/` if the interface changed, and **always** write a new progress note in
   `docs/current-progress/` before you stop (see the session protocol).

### Provider pattern (the important one)

```python
# backend/app/providers/base.py defines the interface.
# backend/app/providers/llm.py wraps Gemini on Agent Platform (Vertex AI).
# Feature code calls the provider, never google.genai directly.
result = await providers.llm.complete_json(
    model=..., prompt_version=..., system=..., user=..., schema=...
)
```

## 7. Workstreams

Three engineers, three lanes (see `docs/technical-design/workstreams.md`):

| Person | Owns |
|---|---|
| A | `web/` — all UI |
| B | `backend/` — API, jobs, agents, reviewers |
| C | `infra/`, `corpus/`, connectors, media, localization, seed |

If you need something from another lane, fake it and keep moving. Never block.

## 8. Gotchas

- GCP has no native hard spending cap. We built a kill switch (`infra/budget.tf`).
- Cloud Text-to-Speech has no IAM role for synthesis; the enabled API is enough.
- Pub/Sub ack deadline max is 600 seconds.
- Speech-to-Text long audio uses **batch** recognition (`chirp_3`, `us` multi-region), not sync.
  STT V2 cannot auto-detect AAC in MP4/MOV/M4A, so those use an explicit decoding config.
- Transcription is triggered by the GCS `object finalized` Pub/Sub push
  (`POST /api/internal/pubsub/video-events`); `POST /assets/{id}/complete` is the fast UX path.
  Both converge on one idempotent `transcribe` job.
- Firebase ToS acceptance is console-only.
- Next.js 16 bundles its own docs and regenerates `web/AGENTS.md`; read them before coding.
- The Firebase default bucket (`habeas-codus.firebasestorage.app`) is **not** used. The app uses
  `habeas-codus-media`.
- **Delete is real, not soft.** `DELETE /projects/{id}` removes the Firestore subtree and every
  GCS object under the project prefix; account deletion removes the whole user tree. Keep new
  project-scoped data under those paths or it will leak (see workflow step 6).

## 9. Where to look

| Question | File |
|---|---|
| Why was a decision made? | `docs/technical-design/README.md` |
| What is the DB shape? | `docs/technical-design/db-design.md`, `contracts/firestore.md` |
| What is the API? | `contracts/openapi.yaml`, `docs/technical-design/api-design.md` |
| What events flow? | `contracts/events.md` |
| How are external calls made? | `docs/technical-design/backend-plan.md` (provider layer) |
| What GCP resources exist? | `infra/RESOURCES.md` |
| What has been done? | `docs/current-progress/` |
