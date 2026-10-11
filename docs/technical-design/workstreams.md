# Repository workstreams

| Lane | Owns |
|---|---|
| A | `web/`: interface, static hosting integration, API consumption and realtime UX |
| B | `backend/`: API, services, jobs, reviewer/provider orchestration and writing |
| C | `infra/`, `corpus/`, `fixtures/`: cloud resources, connectors, media and localization data |

Contracts are shared. Update OpenAPI when endpoints/shapes change and document new persisted
records. Feature code uses providers/adapters; owned data stays under deletion prefixes.
Bun, uv and Terraform are the repository tools. No tests/testing dependencies are added.
Do not commit without the user's instruction.

Read the newest `docs/current-progress/` note before changing files. Write a timestamped
handoff after each meaningful unit: work done, structural changes, decisions/gotchas,
verification scope and next step. Preserve unrelated shared-workspace changes.

The earlier three-week plan proposed broader features and additional worker services.
Current capability/deployment status is in [architecture](../architecture.md), not that
original plan. [Evaluations](../../evals/README.md) and [costs](../costs.md) distinguish
implemented mechanisms from measured quality, impact and spend.
