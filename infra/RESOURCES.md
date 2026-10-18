# Habeas Codus — Deployed Resources

Human-readable inventory of the infrastructure defined in this folder for the single
GCP project `habeas-codus`, region `us-central1`. This describes Terraform definitions,
not live cloud state: definitions alone do not prove what is deployed, and the BigQuery
/ worker cleanup described below was removed from Terraform but still needs a reviewed
`terraform plan` and apply.

Terraform lives in this folder. Run commands from `infra/`.

---

## Project

| Thing | Value |
|---|---|
| Project ID | `habeas-codus` |
| Region | `us-central1` |
| Billing account | `014B5B-1E8419-7A90A3` |
| Terraform state | `gs://habeas-codus-terraform-state`, prefix `creator-studio` |

The API runtime service account has Cloud Translation API User for cross-language dubbing.
Translation and Text-to-Speech APIs are enabled through Terraform with the rest of the runtime
services.

---

## Cloud Storage buckets

| Bucket | What goes in it | Notes |
|---|---|---|
| `habeas-codus-media` | Source videos, transcripts, captions, thumbnails, clips, persona files | Versioning on. CORS allows localhost:3000/8080 plus the deployed web origins. The API signs V4 upload URLs via IAM signBlob, so `creator-studio-api` has `roles/iam.serviceAccountTokenCreator` on itself. This is the one the browser uploads to. |
| `habeas-codus-raw-social` | Reserved for raw connector dumps; the backend does not use it yet | Never read by the browser. |
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
| Security rules | `firestore.rules` (repo root), released as `cloud.firestore`. Deny all direct client access — the backend uses the Admin SDK. |
| Composite index | `projects`: `ownerUid` ASC, `updatedAt` DESC (COLLECTION scope). Required by `GET /projects`. |

Firestore is the **control plane**: users, projects, jobs, transcripts, findings, artifacts,
chat, persona. Big media lives in Cloud Storage. See
`../docs/technical-design/db-design.md`.

Rules and the index are declared in `firestore_rules.tf` and `firestore_indexes.tf`. Applied
directly (Terraform was not installed on the workstation) with:

```bash
# composite index for the projects list query
gcloud firestore indexes composite create \
  --project=habeas-codus --database="(default)" --collection-group=projects \
  --query-scope=collection \
  --field-config=field-path=ownerUid,order=ascending \
  --field-config=field-path=updatedAt,order=descending

# rules: create a ruleset from firestore.rules and point the cloud.firestore release at it
# (or, once firebase-tools is installed: firebase deploy --only firestore:rules)
```

---

## Pub/Sub

### Topics (the events that flow through the system)

| Topic | Meaning | Traffic |
|---|---|---|
| `video-events` | A video finished uploading and needs processing. | Live: GCS `object finalized` notification → push subscription below. |
| `transcription-events` | A transcript is ready (or failed). | Published best-effort; no subscribers. |
| `analysis-events` | An analysis run was requested / a reviewer finished. | Published best-effort; no subscribers. |
| `social-sync-events` | Mapped in `backend/app/events.py` but never published. | None. |
| `artifact-events` | Mapped in `backend/app/events.py` but never published. | None. |
| `localization-events` | Mapped in `backend/app/events.py` but never published. | None. |

### Dead-letter topic

`video-events-dlq` (poison messages after 5 tries).

### Subscriptions (who listens)

| Subscription | Topic | Consumer |
|---|---|---|
| `transcribe-worker-sub` | `video-events` | Push to `POST /api/internal/pubsub/video-events` on the API (OIDC as `creator-studio-transcribe`) |

Only `video-events` has a consumer. The API also publishes `transcription-events` and
`analysis-events` on a best-effort basis; nothing subscribes to them. `social-sync-events`,
`artifact-events` and `localization-events` exist as topics but are never published.
BigQuery datasets, unused worker subscriptions, dead-letter topics and five worker service
accounts were removed from Terraform (`infra/*.tf` has no BigQuery resources); applying
that removal in the cloud is a separate reviewed step.

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
| `meta-app-id` | Meta app ID (not used by the backend yet) |
| `meta-app-secret` | Meta app secret |
| `session-signing-secret` | Signs server sessions |

---

## Service accounts

| Account | What it can do |
|---|---|
| `creator-studio-api` | Firestore read/write, GCS objects, Pub/Sub publish, secret access, Vertex AI, KMS encrypt/decrypt, Speech-to-Text, Firebase Auth admin |
| `creator-studio-transcribe` | Identity for the Pub/Sub push subscription's OIDC token (plus GCS, Firestore, Pub/Sub and Speech roles) |
| `creator-studio-deployer` | Push images to Artifact Registry, deploy Cloud Run |
| `terraform@habeas-codus` | Manages all the above (bootstrap) |
| `service-538724167565@gs-project-accounts` | Cloud Storage's own agent; can publish to `video-events` |

The API runs as `creator-studio-api`; workers run inside that service. Five separate
worker service accounts were removed from Terraform; only the three above plus the
bootstrap and Storage-agent identities remain defined.

---

## Artifact Registry

| Repo | Purpose |
|---|---|
| `creator-studio-containers` | Docker images for the API (workers run inside it). |

Full image path: `us-central1-docker.pkg.dev/habeas-codus/creator-studio-containers`

---

## Budget and kill switch

Google Cloud has no native hard spending cap, so we built one.

| Thing | Value |
|---|---|
| Budget | `Hackathon cap` — ₹17,000 (~$200) on this project |
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

`services.tf` enables only this infrastructure set; anything else the app calls (Gemini
on Vertex AI / Agent Platform, Speech-to-Text, Translation, Text-to-Speech, YouTube Data
and Analytics, Firebase/Identity Toolkit, Cloud Scheduler, Logging/Monitoring/Trace,
Cloud Build) must already be enabled on the project outside this Terraform:

Firestore, Pub/Sub, Cloud Run, Artifact Registry, Cloud Storage, Secret Manager, Cloud
KMS, Cloud Functions, Eventarc, Billing Budgets.

---

## Firebase

Firebase is attached to the `habeas-codus` GCP project (imported, not a separate project).

| Thing | Value |
|---|---|
| Web app | `Creator Studio Web` |
| App ID | `1:538724167565:web:87eb1e0f5245b5079217c4` |
| Auth domain | `habeas-codus.firebaseapp.com` |
| Sign-in | Google enabled. Email/Password is **disabled**; the demo uses passwordless custom tokens |
| Authorized domains | `localhost`, `habeas-codus.firebaseapp.com`, `habeas-codus.web.app` |

### Read-only demo account

The shared demo account `demo@habeascodus.app` (UID `demoCreatorHabeasCodus`) is **passwordless**:
the web client calls `POST /api/demo/session`, which returns a short-lived Firebase custom token
minted via the IAM signBlob API (the API service account has `serviceAccountTokenCreator` on
itself). No password is ever shipped to the browser, and Email/Password sign-in is disabled so
the old shared password cannot be used. Its content was seeded from a real creator with
`backend/scripts/copy_user_content.py`.

The UID is listed in `READ_ONLY_USER_UIDS`, so the API rejects every POST/PUT/PATCH/DELETE from
it with 403, and `DEMO_USER_UID` enables the session endpoint. The web client disables the
matching controls and shows a read-only banner. The landing page shows a one-click "Try the
demo" when `NEXT_PUBLIC_DEMO_ENABLED=true`.

Residual client-SDK actions on the account itself (e.g. `deleteUser`) do not touch any content
(it lives in Firestore/Cloud Storage and survives an Auth deletion); `POST /api/demo/session`
recreates the Auth user if it is missing, so the demo self-heals on the next click.

Web config (public, safe to expose — the API key is an identifier, not a secret):

```json
{
  "projectId": "habeas-codus",
  "appId": "1:538724167565:web:87eb1e0f5245b5079217c4",
  "storageBucket": "habeas-codus.firebasestorage.app",
  "apiKey": "AIzaSyAjWq40FQKv6pN9LJI1glJq6gsfOTMNi7Q",
  "authDomain": "habeas-codus.firebaseapp.com",
  "messagingSenderId": "538724167565",
  "projectNumber": "538724167565"
}
```

Firebase created its own default bucket `habeas-codus.firebasestorage.app`. **Do not use it** — the
app uses `habeas-codus-media` from Terraform.

The Firebase-managed Google OAuth client secret must never be committed. The web app does not need
it.

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
| `firestore_indexes.tf` | Composite indexes (projects list) |
| `firestore_rules.tf` | Firestore security rules ruleset + release |
| `pubsub.tf` | Topics, DLQ, transcription push subscription, GCS notification |
| `kms.tf` | Keyring and key |
| `secrets.tf` | Secret containers |
| `service_accounts.tf` | Runtime service accounts |
| `iam.tf` | Role bindings, GCS publisher, engineer access |
| `artifact_registry.tf` | Container repo |
| `budget.tf` | Budget, notification topic, kill switch function and IAM |
| `killswitch/main.py` | Kill switch source |
| `outputs.tf` | Bucket names, topics, SA emails, etc. |

## Common commands

```bash
cd infra
terraform plan
terraform apply
terraform output
```
