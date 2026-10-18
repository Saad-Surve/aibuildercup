# Resonance infrastructure reference

The project is **`habeas-codus`**. [infra/RESOURCES.md](../../infra/RESOURCES.md) records
resource names/configuration; Terraform definitions live in `infra/`. This document
describes Terraform definitions separately from the deployed runtime; definitions alone do
not establish cloud state.

## Regions and authentication

Infrastructure/Storage/Firestore/KMS/Veo use `us-central1`. STT Chirp 3 uses the `us`
multi-region; Gemini uses configurable `VERTEX_LOCATION=global` by default. Global model
routing is distinct from regional data storage and must not be described as all requests
running in one regional endpoint. Services use ADC; the Cloud Run runtime service account
supplies identity, and developers use `gcloud auth application-default login`.

## Deployment

`.github/workflows/deploy.yml` filters web/backend changes. API builds publish to Artifact
Registry and deploy `creator-studio-api`; web builds with Bun and deploys the static
export to Firebase Hosting. GitHub Workload Identity Federation authenticates deployment
without a long-lived service-account key. Optional YouTube OAuth secrets are attached only
when versions exist. Repository variables can override models, demo and corpus settings.

The API currently uses max-instances **one**, min-instances zero, **4 vCPU / 4 GiB**,
CPU available outside requests, and a 3,600-second request timeout. Transcription,
analysis, captions, dubbing, thumbnails, packaging and publishing run within that service.
Unused worker subscriptions, dead-letter topics and five worker service accounts have been
removed from Terraform, along with BigQuery datasets. The transcription push identity remains.
Cloud cleanup requires a reviewed plan and apply.

Firebase Hosting rewrites `/api/**` to the regional API and project deep links to the
static project shell. WebSockets use the direct Cloud Run origin. `next.config.ts` rewrites
alone do not apply to production static hosting.

## Data and events

| Resource | Current role |
|---|---|
| `habeas-codus-media` | Browser source uploads, project outputs/evidence, personas, user imports and shared preset archive |
| `habeas-codus-corpus` | Provisioned corpus bucket; runtime localization currently reads bundled JSON |
| Raw-social/temp/exports buckets | Provisioned broader design; do not assume every current media path uses them |
| Terraform state bucket | Remote state, prefix `creator-studio` |
| Firestore Native | Owned workflow/evidence data and current channel analytics; deny-all direct client rules |
| Pub/Sub `video-events` | Storage-finalized push to the authenticated API transcription handler |
| Other pipeline topics | Transcription/analysis announcements without consumers; social/artifact/localization topics have no active publishers |
| `video-events-dlq` | Dead-letter destination for the retained transcription push subscription |

Buckets enforce uniform access/public-access prevention. Media/corpus versioning retains
noncurrent generations, with a default 30-day lifecycle; temporary-bucket objects expire
after seven days. The Firebase default bucket is not the app media bucket.

## Security

Firebase authenticates clients; the backend validates ownership and signs short-lived
Storage URLs. Pub/Sub push verifies Google OIDC against configured audience/service account.
Firestore rules block direct client data access. Account/project deletion uses recursive
Firestore trees and current object-prefix deletion; noncurrent versions are not explicitly
purged by the current adapter.

OAuth client secrets are in Secret Manager, and persisted OAuth tokens are encrypted with
Cloud KMS. Local development can use the configured local cipher, which is refused in
production. The API identity carries permissions needed by its in-process workers. The
transcription account supplies the push OIDC identity; the deployer publishes the service.
No secrets belong in Git, public web variables or Terraform variable files.

## Budget and scale

`infra/budget.tf` configures a ₹17,000 budget and Pub/Sub-triggered Cloud Function that can
detach billing at the threshold. Notification/billing latency means it is not a real-time
hard cap. Analysis/image estimates, embedding call slots and Veo reservations provide more
local bounds with different coverage. [Cost documentation](../costs.md) describes actual
rates, guard limits and gaps.

Before increasing instances, add durable worker dispatch, distributed execution leases and
shared realtime fan-out. Atomic job creation alone does not supply these. Before quoting
scale, measure concurrent real uploads/reviews and backlog recovery. Managed vector indexing
and more efficient calendar reads are subsequent changes when bounded scans no longer fit.

## Operations

```bash
cd infra
terraform init
terraform plan
```

Inspect the plan before applying an authorized infrastructure change. This documentation
work does not establish live cloud state. `services.tf` enables only its listed infrastructure
APIs; model, Speech, Translation/TTS, Firebase and YouTube APIs may need separate enablement. Cloud Run/Firebase deployment
configuration lives in GitHub Actions rather than a Terraform Cloud Run service resource.
Monitor accepted model operations/retries, job errors, instance lifetime, data operations,
output storage/egress and billing SKUs. Configured budgets/quotas are not measurements of
actual cost, throughput or model admission reliability.
