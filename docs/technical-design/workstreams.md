# Creator Helper Studio — Three-Engineer Workstream Plan

Hackathon context: 2–3 weeks, 3 engineers, AI-heavy coding. The plan is built so nobody
blocks anybody after Day 1.

## 1. The one rule

Freeze the contracts on Day 1 (API shape, Firestore shape, event envelope, fixture format).
After that, every person develops against fake data:

- Engineer A builds against MSW mocks (frontend).
- Engineer B builds against cassettes (backend / AI).
- Engineer C owns the fixtures and cassettes.

If you need something from someone else's lane, fake it and keep moving.

## 2. Three lanes

| | Engineer A — Experience | Engineer B — Brains | Engineer C — Plumbing |
|---|---|---|---|
| Owns | Everything you see and click: Next.js app, Firebase Auth, onboarding, upload, timeline + heatmap, findings, chat UI, gallery, localization UI, audience insights | FastAPI API, job/queue orchestration, transcription, all reviewers + coordinator, chat agent + tools, generation flows (shorts, thumbnails, captions, text, Veo) | Firestore, mock/cassette layer, YouTube/Meta connectors, BigQuery + sentiment, FFmpeg media worker, localization pipeline, Terraform, CI/CD, observability |
| Folder | `web/` | `backend/` | `infra/`, `corpus/`, `fixtures/` |
| Cloud Run surfaces | `creator-studio-web` | `creator-studio-api`, `creator-studio-transcribe-job`, `creator-studio-analysis-worker` | `creator-studio-social-sync-job`, `creator-studio-media-job`, `creator-studio-localization-job` |

Why these boundaries:

- A only consumes the API and never touches GCP internals.
- B owns everything that makes an LLM call in the request path.
- C owns infra, storage, analytics, and heavy media. Transcription stays with B because it is
  in the demo spine; FFmpeg media and localization stay with C because they share a toolchain.

## 3. Repo layout

```text
creator-studio/
├── web/          Engineer A
├── backend/      Engineer B    api/ workers/ agents/ providers/
├── infra/        Engineer C    terraform/
├── corpus/       Engineer C    global glossaries
├── fixtures/     shared        cassettes/ seed/ demo-video/
├── contracts/    shared        openapi.yaml, events.md, firestore.md
└── README.md
```

## 4. Phases

### Phase 0 — Day 1, all three

1. Freeze `contracts/openapi.yaml`, Pydantic models, Firestore schema, Pub/Sub envelope, cassette format.
2. Generate the TypeScript API client from OpenAPI so A and B cannot drift.
3. C scaffolds the provider/cassette layer and `seed.py` skeleton.
4. A scaffolds Next.js + MSW. B scaffolds FastAPI + worker entrypoints.

### Phase 1 — Week 1: demo spine

Goal: `login -> onboarding -> upload -> transcript -> timeline` on seeded data.

- A: auth, app shell, onboarding/persona preview, resumable direct-to-GCS upload, workspace shell, transcript + basic timeline.
- B: API skeleton, Firebase auth middleware + ownership checks, jobs/SSE, transcription worker (STT `chirp_3`), transcript API + canonical JSON/VTT.
- C: Firestore rules/indexes/emulator, provider + cassette layer, seed script + demo video, Terraform modules, CI, hello-world deploy.

Gate: end-to-end on fixtures, and real STT recorded once on the demo video to produce a cassette.

### Phase 2 — Week 2: differentiators

- A: SVG heatmap tracks, finding popover/drawer, deep-review trigger, streaming chat UI, suggested prompts.
- B: reviewer base + 13 reviewers + coordinator + tiered fan-out + heatmap aggregation + calibration; ADK project agent + tools + context builder; shorts/thumbnail/text generation flows.
- C: YouTube + Meta connectors + normalization, BigQuery load + comment sentiment + audience aggregates, FFmpeg media worker, start corpus ingestion.

Gate: heatmap + chat + one rendered artifact end-to-end on cassettes; connector + sentiment visible in BigQuery on fixture data.

### Phase 3 — Week 3: breadth + polish

- A: artifact gallery, localization comparison UI, audience insights, responsive + accessibility pass, demo scenario picker.
- B: deep multimodal segment review, Veo intros/outros, cost-cap meter, AI eval harness.
- C: localization pipeline (glossary + corpus + TTS + duration-normalized mux), audit + account deletion, observability/alerts, deploy hardening.

Gate: full demo dry-run; flip `MOCK_MODE=off` feature-by-feature for the live moment.

## 5. Working together

- Keep the demo branch deployed the whole time so integration breakage shows up early.
- Small PRs. CI gate = lint + typecheck + unit tests.
- Additive contract changes only after Phase 0. A breaking change needs a quick team huddle.
- Use AI to write code aggressively, but read what it generates. Every generated fixture is human reviewed.
- Daily 15-minute sync.

## 6. Ownership of shared surfaces

| Surface | Proposes | Consumes | Reviews |
|---|---|---|---|
| API contract | B | A | C |
| Firestore schema | C | B | A |
| Cassettes/fixtures | each owner adds their own | all | C maintains loader |
| Terraform | C | all | owner |
