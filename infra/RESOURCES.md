# Habeas Codus — Deployed Resources

Human-readable inventory of everything provisioned for the hackathon. Everything here lives in the
single GCP project `habeas-codus`, region `us-central1`.

Terraform lives in this folder. Run commands from `infra/`.

---

## Project

| Thing | Value |
|---|---|
| Project ID | `habeas-codus` |
| Region | `us-central1` |
| Billing account | `014B5B-1E8419-7A90A3` |
| Terraform state | `gs://habeas-codus-terraform-state`, prefix `creator-studio` |

---

## Cloud Storage buckets

| Bucket | What goes in it | Notes |
|---|---|---|
| `habeas-codus-media` | Source videos, transcripts, captions, thumbnails, clips, persona files | Versioning on. CORS open for localhost:3000/8080. This is the one the browser uploads to. |
| `habeas-codus-raw-social` | Raw JSON dumps from YouTube/Meta connectors | Never read by the browser. |
| `habeas-codus-temp` | Scratch space for FFmpeg (extracted clips, frames, audio) | Auto-deleted after 7 days. |
| `habeas-codus-exports` | Zipped bundles the user downloads | |
| `habeas-codus-corpus` | Localization glossaries and the "trap list" (TSV) | Versioned. Backs the translation differentiator. |
| `habeas-codus-terraform-state` | Terraform remote state | Bootstrap bucket, created by hand. |

All buckets: uniform bucket-level access on, public access prevention enforced.

---

## Firestore

| Thing | Value |
|---|---|
| Database | `(default)` |
| Mode | Native |
| Location | `us-central1` |

Firestore is the **control plane**: users, projects, jobs, transcripts, findings, artifacts,
chat, persona. Big media lives in Cloud Storage, analytics live in BigQuery. See
`../docs/technical-design/db-design.md`.

---

## Pub/Sub

### Topics (the events that flow through the system)

| Topic | Meaning |
|---|---|
| `video-events` | A video finished uploading and needs processing. |
| `transcription-events` | A transcript is ready (or failed). |
| `analysis-events` | An analysis run was requested / a reviewer finished. |
| `social-sync-events` | A platform sync was requested. |
| `artifact-events` | A media artifact (short, thumbnail, etc.) should be generated. |
| `localization-events` | A localization/dubbing job should run. |

### Dead-letter topics (where poison messages go after 5 tries)

`video-events-dlq`, `analysis-events-dlq`, `social-sync-events-dlq`, `artifact-events-dlq`

### Subscriptions (who listens)

| Subscription | Topic | Consumer |
|---|---|---|
| `transcribe-worker-sub` | `video-events` | Transcribe worker |
| `analysis-worker-sub` | `analysis-events` | Analysis worker |
| `social-sync-worker-sub` | `social-sync-events` | Social sync worker |
| `media-worker-sub` | `artifact-events` | Media (FFmpeg) worker |
| `localization-worker-sub` | `localization-events` | Localization worker |

Ack deadline is 600s on all of them.

---

## BigQuery

| Dataset | Tables | Purpose |
|---|---|---|
| `creator_studio_social` | `posts`, `metrics`, `comments`, `audience_aggregates` | Normalized platform data pulled by the connectors. |
| `creator_studio_ai` | `comment_sentiment`, `agent_runs`, `glossary_terms`, `translation_traps` | Sentiment results, model usage/cost, and the localization corpus. |
| `creator_studio_audit` | `data_access_events` | Who touched what. |

---

## Cloud KMS

| Resource | Purpose |
|---|---|
| Keyring `creator-studio-keyring` | Holds the key used to encrypt user OAuth tokens. |
| Key `user-token-key` | Envelope-encrypts refresh tokens before they touch Firestore. Rotates every 90 days. |

---

## Secret Manager

These exist but are **empty** until you add versions (values). Empty secrets are intentional — no
credentials in Terraform state.

| Secret | Holds |
|---|---|
| `youtube-oauth-client-id` | YouTube OAuth client ID |
| `youtube-oauth-client-secret` | YouTube OAuth client secret |
| `meta-app-id` | Meta app ID |
| `meta-app-secret` | Meta app secret |
| `session-signing-secret` | Signs server sessions |

---

## Service accounts

| Account | What it can do |
|---|---|
| `creator-studio-api` | Firestore read/write, GCS objects, Pub/Sub publish, secret access, Vertex AI, KMS encrypt/decrypt |
| `creator-studio-transcribe` | GCS read/write, Firestore write, Pub/Sub pub/sub, Speech-to-Text |
| `creator-studio-analysis` | GCS read, Firestore read/write, Vertex AI, Pub/Sub pub/sub |
| `creator-studio-social-sync` | Secret access, KMS decrypt, BigQuery write, GCS object create, Firestore read, Pub/Sub subscribe |
| `creator-studio-media` | GCS read/write, Firestore write, Pub/Sub pub/sub |
| `creator-studio-localization` | GCS read/write, Translation, Vertex AI, Firestore write, Pub/Sub subscribe |
| `creator-studio-deployer` | Push images to Artifact Registry, deploy Cloud Run |
| `terraform@habeas-codus` | Manages all the above (bootstrap) |
| `service-538724167565@gs-project-accounts` | Cloud Storage's own agent; can publish to `video-events` |

Each runtime account is meant to be attached to exactly one Cloud Run service/job.

---

## Artifact Registry

| Repo | Purpose |
|---|---|
| `creator-studio-containers` | Docker images for the API and all workers. |

Full image path: `us-central1-docker.pkg.dev/habeas-codus/creator-studio-containers`

---

## Budget and kill switch

Google Cloud has no native hard spending cap, so we built one.

| Thing | Value |
|---|---|
| Budget | `Hackathon cap` — ₹8,500 (~$100) on this project |
| Alerts | 50%, 80%, 100%, and forecasted-100% |
| Notification topic | `budget-alerts` |
| Function | `budget-killswitch` (Cloud Function gen2, `us-central1`) |
| Guard service account | `creator-studio-budget-guard@habeas-codus.iam.gserviceaccount.com` |
| Trigger | Eventarc on `budget-alerts` |

How it works: the budget publishes to `budget-alerts` as spend crosses thresholds. The function
reads `costAmount` vs `budgetAmount`; once cost reaches the budget it calls the Cloud Billing API
and detaches billing from the project. That stops all billable serving until billing is manually
re-attached.

To temporarily disable the stop (log only) without changing code:

```bash
cd infra
terraform apply -var 'killswitch_dry_run=true'   # observe only
terraform apply -var 'killswitch_dry_run=false'  # armed again
```

To change the threshold, edit `budget_amount` in `variables.tf` and re-apply.

To re-attach billing after it fires:

```bash
gcloud billing projects link habeas-codus --billing-account=014B5B-1E8419-7A90A3
```

---

## Enabled APIs

Storage, Firestore, Pub/Sub, BigQuery, Cloud Run, Artifact Registry, Cloud Build, Vertex AI,
Speech-to-Text, Translation, Text-to-Speech, Secret Manager, Cloud KMS, Cloud Scheduler,
YouTube Data, YouTube Analytics, Logging, Monitoring, Cloud Trace, Firebase, Identity Toolkit.

---

## Terraform file map

| File | Contains |
|---|---|
| `versions.tf` | Terraform + provider versions |
| `backend.tf` | GCS remote state |
| `providers.tf` | Google provider, impersonates the Terraform SA |
| `variables.tf` | Project, region, allowed origins, engineer emails |
| `services.tf` | Required APIs |
| `storage.tf` | Buckets, versioning, lifecycle, CORS |
| `firestore.tf` | Firestore database |
| `pubsub.tf` | Topics, DLQs, subscriptions |
| `bigquery.tf` | Datasets and tables |
| `kms.tf` | Keyring and key |
| `secrets.tf` | Secret containers |
| `service_accounts.tf` | Runtime service accounts |
| `iam.tf` | Role bindings, GCS publisher, engineer access |
| `artifact_registry.tf` | Container repo |
| `budget.tf` | Budget, notification topic, kill switch function and IAM |
| `killswitch/main.py` | Kill switch source |
| `outputs.tf` | Bucket names, datasets, SA emails, etc. |

## Common commands

```bash
cd infra
terraform plan
terraform apply
terraform output
```
