# Resonance technical reference

Start with [the implemented architecture](../architecture.md), then
[measured evaluations](../../evals/README.md) and [costs](../costs.md).
This package describes the current code, updated 11 October 2026. Future work is labeled;
older timestamped progress notes retain the decisions and validation available at the time.

| Reference | Contents |
|---|---|
| [Backend](backend-plan.md) | Runtime boundaries, jobs, transcription, nine reviewers, heatmaps, writing and media |
| [Frontend](frontend-plan.md) | Static Next.js application, player/workspace, editor, library, calendar and realtime |
| [Packaging](packaging-plan.md) | Saved YouTube listings, grounded visual inserts, rendering and paid reservations |
| [API](api-design.md) | Registered route families, auth, asynchronous behavior and planned contract paths |
| [Database](db-design.md) | Implemented owned hierarchy, source/version references and lifecycle |
| [Diagrams](diagrams.md) | Actual deployment and editorial/retrieval/media flows |
| [Infrastructure](infra-plan.md) | Terraform, CI/CD, regions, security, resource roles and scale constraints |
| [Fixtures and demo](mock-and-seed.md) | Real local media, read-only demo and creator import |
| [Localization corpus](localization-corpus.md) | Bundled terminology/traps, project glossary and adaptation |

Wire payloads are defined by [OpenAPI](../../contracts/openapi.yaml); persisted shapes by
[Firestore contracts](../../contracts/firestore.md), schemas and service write paths.
[Events](../../contracts/events.md) describe Pub/Sub and WebSocket envelopes.
The manually maintained web types/client must stay aligned with those contracts.

Google calls use ADC and provider boundaries. Infrastructure is regional in `us-central1`;
STT uses `us`, Gemini defaults to `global`, and Veo is regional. The current runtime is
FastAPI with custom Python orchestration; installed ADK is not evidence of an ADK Runner.
Workers run in the single Cloud Run API instance. BigQuery and extra event infrastructure
are provisioned expansion paths, not current dashboards or separately deployed workers.

Full automatic shorts, video-project chat and connectors beyond YouTube are future work.
Draft writing chat, generated listings and source-linked visual inserts have distinct
implemented paths. For the latest work and deployment state, read the newest
[progress note](../current-progress/).
