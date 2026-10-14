# Resonance technical reference

This index describes the current source: upload and transcription, specialist and rubric
review, editor and footage adjudication, creator decisions, rough cuts and re-review,
creator retrieval, writing, media and publishing. Start with [architecture](../architecture.md);
[HANDOFF.md](../current-progress/HANDOFF.md) is the single current status document and
separates source changes from deployed state and live verification.

| Reference | Contents |
|---|---|
| [Backend](backend-plan.md) | Providers, jobs, resumable STT, editorial stages, interest calibration, writing and publishing |
| [Frontend](frontend-plan.md) | Static Next.js workspace, decisions, rough-cut preview/comparison, library, drafts and calendar |
| [Packaging](packaging-plan.md) | Saved YouTube listings, grounded visual inserts, rendering and paid reservations |
| [API](api-design.md) | Registered routes, ownership, asynchronous jobs and planned contract paths |
| [Database](db-design.md) | Owned hierarchy, editorial metadata, source revisions, calibration and deletion |
| [Diagrams](diagrams.md) | Deployment, review/re-review, retrieval, media and lifecycle flows |
| [Infrastructure](infra-plan.md) | Terraform scope, CI/CD, regions, security and single-instance constraints |
| [Fixtures and demo](mock-and-seed.md) | Local originals, read-only demo, creator imports and editorial evaluation sets |
| [Localization corpus](localization-corpus.md) | Bundled terminology/traps, project glossary and adaptation |

Wire shapes are in [OpenAPI](../../contracts/openapi.yaml), persisted shapes in
[Firestore](../../contracts/firestore.md), and event envelopes in
[Events](../../contracts/events.md). Web types/client are manually maintained.
[Reviewer prompts](../reviewer-prompts.md), [evaluations](../../evals/README.md) and
[costs](../costs.md) document model instructions, evidence and spending bounds.

Google calls use ADC through providers. Infrastructure uses `us-central1`; STT uses `us`,
Gemini defaults to `global`, and Veo is regional. Custom Python orchestration runs workers
inside one Cloud Run API instance. BigQuery datasets, unused worker subscriptions and five
worker service accounts have been removed from Terraform; application of that cleanup is
an operational step recorded in HANDOFF.md.

Automatic shorts and generic video-project chat remain future work. Draft chat, generated
listings, rough-cut rendering and synchronous Substack/Medium/Reddit cross-posting exist.
Substack can request platform-side scheduling; there is no local scheduled cross-post worker.
