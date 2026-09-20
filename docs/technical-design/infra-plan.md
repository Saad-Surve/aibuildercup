# Creator Helper Studio — Infrastructure, Terraform, Users, and IAM Plan

## 1. Environment model

Use one GCP project and one hackathon environment:

~~~text
creator-studio-hackathon
~~~

Use `us-central1` for every regional service:

~~~text
REGION=us-central1
~~~

Why central1 and not east1: Speech-to-Text Chirp 2/3 is generally available in `us-central1` but
not `us-east1`, and Veo, Imagen, and Text-to-Speech documentation all use `us-central1`. One
region keeps Terraform and latency simple.

Do not create separate dev/prod projects or Terraform workspaces for the hackathon. Local development can use emulators, but deployed resources all belong to this single environment.

## 2. Terraform repository

~~~text
infra/
├── bootstrap/
│   ├── state-bucket.tf
│   ├── terraform-service-account.tf
│   └── outputs.tf
├── modules/
│   ├── project-services/
│   ├── storage/
│   ├── firestore/
│   ├── pubsub/
│   ├── bigquery/
│   ├── iam/
│   ├── secrets/
│   ├── cloud-run/
│   ├── cloud-run-job/
│   ├── monitoring/
│   └── budgets/
├── backend.tf
├── providers.tf
├── main.tf
├── variables.tf
├── outputs.tf
└── README.md
~~~

## 3. Bootstrap Terraform state

Create the state bucket once before applying the main configuration:

~~~hcl
resource "google_storage_bucket" "terraform_state" {
  name                        = "creator-studio-terraform-state"
  location                    = "US-CENTRAL1"
  uniform_bucket_level_access = true

  versioning {
    enabled = true
  }

  lifecycle_rule {
    condition {
      num_newer_versions = 10
    }
    action {
      type = "Delete"
    }
  }
}
~~~

Then configure:

~~~hcl
terraform {
  backend "gcs" {
    bucket = "creator-studio-terraform-state"
    prefix = "creator-studio/hackathon"
  }
}
~~~

Use this single state prefix for the hackathon environment.

## 4. APIs to enable

~~~text
serviceusage.googleapis.com
iam.googleapis.com
iamcredentials.googleapis.com
cloudresourcemanager.googleapis.com
run.googleapis.com
artifactregistry.googleapis.com
cloudbuild.googleapis.com
storage.googleapis.com
firestore.googleapis.com
pubsub.googleapis.com
bigquery.googleapis.com
aiplatform.googleapis.com
speech.googleapis.com
translate.googleapis.com
texttospeech.googleapis.com
secretmanager.googleapis.com
cloudkms.googleapis.com
cloudscheduler.googleapis.com
youtube.googleapis.com
youtubeanalytics.googleapis.com
~~~

Enable Transcoder API only if the team chooses it instead of FFmpeg Cloud Run Jobs.

## 5. Storage buckets

Create separate buckets in us-central1:

~~~text
creator-studio-hackathon-media
creator-studio-hackathon-raw-social
creator-studio-hackathon-temp
creator-studio-hackathon-exports
creator-studio-hackathon-corpus
~~~

Bucket policies:

- Uniform bucket-level access.
- Public access prevention.
- Object versioning for persona files and editable artifacts.
- Lifecycle deletion for temporary media.
- Retention rules based on product policy.
- CORS policy allowing only web application origins.

Object prefixes:

~~~text
users/{uid}/projects/{projectId}/source/
users/{uid}/projects/{projectId}/transcripts/
users/{uid}/projects/{projectId}/analysis/
users/{uid}/projects/{projectId}/artifacts/
users/{uid}/profile/
corpus/global/{sourceLang}-{targetLang}/
corpus/trap-list/{sourceLang}-{targetLang}/
~~~

## 6. Pub/Sub resources

Create topics:

~~~text
video-events
transcription-events
analysis-events
social-sync-events
artifact-events
localization-events
~~~

Create subscriptions:

~~~text
transcribe-worker-sub
analysis-worker-sub
social-sync-worker-sub
media-worker-sub
localization-worker-sub
~~~

Create dead-letter topics:

~~~text
video-events-dlq
analysis-events-dlq
social-sync-events-dlq
artifact-events-dlq
~~~

Set retry policies and maximum delivery attempts. Workers must be idempotent because Pub/Sub delivery can repeat.

## 7. BigQuery resources

Create datasets:

~~~text
creator_studio_social
creator_studio_ai
creator_studio_audit
~~~

Tables:

~~~text
creator_studio_social.posts
creator_studio_social.metrics
creator_studio_social.comments
creator_studio_social.audience_aggregates
creator_studio_ai.comment_sentiment
creator_studio_ai.agent_runs
creator_studio_ai.glossary_terms
creator_studio_ai.translation_traps
creator_studio_audit.data_access_events
~~~

Configure partitioning by observation or ingestion date, clustering by owner_uid and platform, expiration for raw staging tables, and backend-only query access.

## 8. Firestore setup

Create a Firestore Native database in the selected region. Deploy:

- Firestore security rules.
- Composite indexes.
- Emulator configuration for local development.

Client-readable data:

~~~text
users/{uid}
users/{uid}/projects/{projectId}
selected transcript, analysis, artifact, and chat documents
~~~

Client-denied data:

~~~text
connections
token references
raw sync data
internal job events
~~~

The API uses the Admin SDK and still performs explicit ownership checks.

## 9. Human users and groups

Do not grant each engineer permanent project Owner access.

The owner should first collect the Google account email for each engineer. GCP IAM does not create ordinary personal Google accounts; engineers must already have Google accounts, or the owner must provision them through Google Workspace or Cloud Identity.

Create Google Groups:

~~~text
creator-studio-engineers@example.com
creator-studio-admins@example.com
creator-studio-viewers@example.com
~~~

Add each engineer to the engineering group. Grant access through groups so membership changes do not require editing project IAM repeatedly.

Suggested human access:

| Group | Roles |
|---|---|
| Engineers | Viewer, Cloud Run Developer, Artifact Registry Writer, Logs Viewer, Firebase development access |
| Admins | Project IAM Admin or carefully scoped equivalent, Service Usage Admin, Terraform state access |
| Viewers | Viewer, Logs Viewer |

For a short hackathon, the owner may temporarily grant roles/editor in this hackathon project, but this access should be removed after the event.

For a small team without Google Groups, direct user bindings can be applied temporarily:

~~~bash
gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member="user:engineer-one@example.com" \
  --role="roles/viewer"

gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member="user:engineer-one@example.com" \
  --role="roles/run.developer"

gcloud projects add-iam-policy-binding "$PROJECT_ID" \
  --member="user:engineer-two@example.com" \
  --role="roles/artifactregistry.writer"
~~~

Use the group-based approach where available. Direct bindings are acceptable for quickly onboarding the three hackathon engineers. Record each engineer's responsibility in the access register:

| Engineer | Primary responsibility | GCP access |
|---|---|---|
| Engineer 1 | Frontend, Firebase, project UI | Viewer, Cloud Run Developer, Firebase development access |
| Engineer 2 | FastAPI, ADK, AI workers | Viewer, Cloud Run Developer, Vertex AI user, Logs Viewer |
| Engineer 3 | Connectors, BigQuery, media workers | Viewer, Cloud Run Developer, BigQuery Data Editor on the hackathon dataset, Logs Viewer |

After the event, remove temporary direct bindings and keep only group-based or role-specific access.

## 10. Service accounts

Create one service account per runtime responsibility:

~~~text
creator-studio-api@project.iam.gserviceaccount.com
creator-studio-transcribe@project.iam.gserviceaccount.com
creator-studio-analysis@project.iam.gserviceaccount.com
creator-studio-social-sync@project.iam.gserviceaccount.com
creator-studio-media@project.iam.gserviceaccount.com
creator-studio-localization@project.iam.gserviceaccount.com
creator-studio-deployer@project.iam.gserviceaccount.com
creator-studio-terraform@project.iam.gserviceaccount.com
~~~

## 11. IAM matrix

| Service account | Required access |
|---|---|
| API | Firestore read/write, Storage object create/read, Pub/Sub publish, Secret Manager accessor, Vertex AI user, KMS encrypt/decrypt |
| Transcribe | Storage read/write, Speech client, Firestore write, Pub/Sub publish/subscribe |
| Analysis | Storage read, Firestore read/write, Vertex AI user, Pub/Sub publish/subscribe |
| Social sync | Secret Manager accessor, KMS decrypt, BigQuery data editor, Storage object creator, Firestore connection read |
| Media | Storage read/write, Firestore write, Pub/Sub publish/subscribe |
| Localization | Storage read/write, Translation user, Text-to-Speech user, Vertex AI user, Firestore write |
| Deployer | Artifact Registry writer, Cloud Run admin/developer, Service Account User on runtime accounts |
| Terraform | Service Usage Admin, Storage admin for managed buckets, Firestore admin, Pub/Sub admin, BigQuery admin, Secret Manager admin, IAM service account admin |

Use resource-level IAM wherever possible instead of project-wide roles.

## 12. Secrets and encryption

Create Secret Manager entries:

~~~text
youtube-oauth-client-id
youtube-oauth-client-secret
meta-app-id
meta-app-secret
session-signing-secret
~~~

Create a Cloud KMS key ring and key for user OAuth token encryption:

~~~text
creator-studio-keyring
└── user-token-key
~~~

Do not put user refresh tokens directly into source code. Store encrypted token material in Firestore and use KMS for envelope encryption.

## 13. Cloud Run services and jobs

Services:

~~~text
creator-studio-web
creator-studio-api
~~~

Jobs or workers:

~~~text
creator-studio-transcribe-job
creator-studio-analysis-worker
creator-studio-social-sync-job
creator-studio-media-job
creator-studio-localization-job
~~~

Configure minimum/maximum instances, job-specific service accounts, Secret Manager references, and strict concurrency limits for AI spend.

The API must never perform long transcription or video rendering synchronously.

## 14. Artifact Registry and CI/CD

Create repository:

~~~text
creator-studio-containers
~~~

Pipeline:

~~~text
Pull request
  -> lint
  -> type check
  -> unit tests
  -> frontend build
  -> backend container build

main branch
  -> build images
  -> push Artifact Registry
  -> terraform plan
  -> terraform apply
  -> deploy hackathon environment
~~~

Use the deployer service account in CI instead of a personal credential, and authenticate through
Workload Identity Federation rather than a downloaded key (see section 18).

## 15. OAuth owner setup

### Firebase

- Create Firebase web application.
- Enable Google provider.
- Add local and hackathon authorized domains.
- Configure Firebase project access for the team.

### YouTube

- Configure OAuth consent screen.
- Enable YouTube Data API and YouTube Analytics API.
- Create a web OAuth client.
- Add exact callback URLs.
- Add test users.
- Store client credentials in Secret Manager.

### Meta

- Create Meta developer application.
- Add Instagram/Facebook products.
- Create test professional accounts.
- Configure callback URLs.
- Request analytics/comment permissions.
- Prepare privacy policy and data deletion callback.
- Complete App Review only if the app is opened beyond test accounts.

## 16. Observability and budgets

Create alerts for:

~~~text
Cloud Run 5xx rate
Pub/Sub dead-letter messages
Failed Cloud Run Jobs
Vertex AI quota errors
Speech-to-Text failures
BigQuery query cost
Storage growth
OAuth refresh failures
~~~

Create budget alerts at 50%, 80%, and 100%.

Log these fields consistently:

~~~text
request_id
owner_uid_hash
project_id
job_id
event_id
model
prompt_version
input_tokens
output_tokens
latency_ms
error_code
~~~

Never log access tokens, refresh tokens, signed URLs, raw private video content, or full private comments.

## 17. Owner execution checklist

1. Collect both engineers' Google account emails (they need real accounts; Cloud Identity or Workspace if you want to create them).
2. Create one GCP project for the hackathon and attach billing.
3. Create the engineering and admin Google Groups, or plan temporary direct bindings.
4. Create the Terraform state bucket and the Terraform service account.
5. Enable the required APIs.
6. Apply Storage, Firestore (Native, us-central1), Pub/Sub, BigQuery, KMS, Secret Manager, and IAM Terraform in us-central1.
7. Create the Firebase application and enable Google sign-in; add localhost and the demo domain as authorized domains.
8. **Request Veo / Imagen / GPU quota on day zero.** Approval can take days.
9. Create the YouTube OAuth consent screen, a test channel, and test users.
10. Create the Meta developer app and test accounts. Assume App Review will not clear in time; plan on fixtures.
11. Add all OAuth credentials and the session secret to Secret Manager.
12. Configure Artifact Registry and CI/CD using Workload Identity Federation (no key files).
13. Deploy the hello-world API and web app.
14. Verify direct Cloud Storage upload, Pub/Sub delivery, and Cloud Run worker execution.
15. Verify Vertex AI, Speech-to-Text, Translation, and Text-to-Speech access.
16. Run `seed.py --demo` and confirm a full demo workspace renders.
17. Configure budgets, logs, alerts, dead-letter topics, and Cloud Run max-instance caps.
18. Add privacy policy, terms, and deletion flow before external testing.

## 18. Workload Identity Federation for CI

Do not create long-lived service account keys for CI. Set up Workload Identity Federation so the
CI provider federates into `creator-studio-deployer`:

~~~text
CI provider OIDC  ->  Workload Identity Pool  ->  creator-studio-deployer
~~~

Grant the deployer `roles/iam.workloadIdentityUser` on its own service account and nothing more.
This removes the most common hackathon secret-leak failure mode.

## 19. Quotas to request on day zero

These have lead time and will silently block the demo if ignored:

~~~text
Veo video generation access / quota
Imagen image generation quota
Vertex AI Gemini per-region quota
Speech-to-Text batch quota
Cloud Run CPU / GPU quota in us-central1
YouTube Data API daily quota (default 10,000 units is small for a full channel sync)
~~~

For YouTube specifically, cap the connector's page size and sync window, or the default quota
will be exhausted in a single run.

## 20. Cost and demo-safety controls

- Budget alerts at 50%, 80%, and 100%.
- Cloud Run max instances capped on the API and every AI worker.
- A per-project cost meter in Firestore (`usagePeriods`) and a hard concurrency semaphore in the
  analysis coordinator.
- Reject an analysis run whose projected cost exceeds the project cap.
- Veo is the most expensive feature by far (roughly $0.15 to $0.40 per second). Keep it on
  cassettes by default and enable it live only for the demo.
- The demo runs against `seed.py --demo` data, never a real creator's private content.
