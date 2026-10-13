# Local setup: Habeas Codus (Creator Helper Studio)

This guide takes you from a clean machine to a running local app: `web/` talking to
`backend/`. Both use the real Google Cloud services: Gemini on Agent Platform (Vertex AI),
Speech-to-Text, Cloud Storage, Firestore, Pub/Sub and Firebase Auth.

> Read `AGENTS.md` first, then `docs/technical-design/README.md`. This guide only covers
> how to get the app running locally.

There are two tracks:

- **Track A: use the existing `habeas-codus` GCP project (recommended).** You need access
  to the shared project and a login. This is the fastest path, because everything is
  already provisioned.
- **Track B: create your own GCP project.** You provision Firestore, buckets, Pub/Sub,
  Firebase and the rest yourself, mostly through Terraform. It is much more work and is
  covered in [Part 5](#part-5-track-b-create-your-own-gcp-project).

---

## 0. Architecture summary (what runs locally)

- `web/` is a Next.js 16 static-export frontend (Bun). It signs the user in with
  **Firebase Auth** (Google provider) and calls the backend at `http://localhost:8080/api`
  with a Firebase ID token.
- `backend/` is FastAPI (uv). It verifies the ID token with **Firebase Admin**, reads and
  writes **Firestore**, uploads and reads **Cloud Storage**, calls **Vertex AI** (Gemini)
  for reviewers, transcript repair and drafting, and uses **Speech-to-Text V2** (`chirp_3`,
  `us` multi-region) for transcription.
- **Workers run in-process locally** through FastAPI `BackgroundTasks`. On upload complete,
  the API runs the transcribe worker itself and then the analysis worker. It also attempts
  to publish Pub/Sub events on a best-effort basis. A publish failure is logged, not fatal.
  You do not need a separate worker process or the Pub/Sub push endpoint locally.
- Local development calls the real GCP project, so you need real credentials (Application
  Default Credentials). This repo has no emulator or mock mode.

---

## 1. Prerequisites

| Tool | Version / notes | Why |
|---|---|---|
| **Google Cloud SDK (`gcloud`)** | any recent | auth, ADC and project access |
| **uv** | `>= 0.5` | backend package manager and Python 3.12 |
| **Bun** | `1.4.x` (the repo pins `bun@1.4.2`) | web package manager and dev server |
| **Git** | any | clone |
| **FFmpeg + ffprobe** | on `PATH` | reviewer footage tools and caption burn-in |
| **Terraform** (Track B only) | `1.6+` | provisioning GCP |
| **Docker** (optional) | only for the deploy image | not needed to run locally |

Install commands, by OS:

```bash
# gcloud: Windows (winget) / macOS (brew)
winget install --id Google.CloudSDK -e
# brew install --cask google-cloud-sdk

# uv
# Windows (PowerShell)
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
# macOS/Linux
curl -LsSf https://astral.sh/uv/install.sh | sh

# Bun
# Windows (PowerShell)
powershell -c "irm bun.sh/install.ps1 | iex"
# macOS/Linux
curl -fsSL https://bun.sh/install | bash

# FFmpeg: Windows (winget) / macOS (brew)
winget install Gyan.FFmpeg
# brew install ffmpeg

# Terraform: Windows (winget) / macOS (brew)
winget install Hashicorp.Terraform
# brew install terraform
```

Verify the installs:

```bash
git --version
gcloud --version
uv --version
bun --version
ffmpeg -version && ffprobe -version
```

> Do not run `npm`, `pip`, `poetry` or `yarn`. `web/` uses Bun only, and `backend/` uses uv
> only. This is a hard rule in `AGENTS.md`, and stray lockfiles cause real breakage. Run
> `bun` only from inside `web/`.

---

## Part 2: Credentials and Google access

These steps are the same for Track A and Track B. Track B runs them against your own project.

### 2.1 Log in with your Google account

```bash
# 1. Log in to gcloud in the browser (the "gcloud CLI" login)
gcloud auth login

# 2. Point gcloud at the project
gcloud config set project habeas-codus

# 3. Application Default Credentials. The backend uses this one.
gcloud auth application-default login

# 4. Tell ADC which project to bill quota to (avoids "quota project" warnings and errors)
gcloud auth application-default set-quota-project habeas-codus
```

The backend never reads a service-account JSON file locally. Every Google SDK call
(`google.genai`, `google.cloud.storage`, `google.cloud.firestore`, `google.cloud.speech_v2`,
`firebase_admin`) uses the ADC created in step 3.

### 2.2 Confirm you have access

On the `habeas-codus` project you need at least Viewer or Editor access, plus these service
roles on your user account:

| Service | Role your user needs | Notes |
|---|---|---|
| Firestore | `roles/datastore.user` | read and write documents |
| Cloud Storage | `roles/storage.objectAdmin` on `habeas-codus-media` (and `-corpus`) | read and write objects |
| Vertex AI / Agent Platform | `roles/aiplatform.user` | Gemini calls |
| Speech-to-Text | `roles/speech.client` and `roles/serviceusage.serviceUsageConsumer` | `chirp_3` batch |
| Pub/Sub | `roles/pubsub.publisher` on the topics | best-effort events |
| Firebase Auth | Firebase Admin SDK works with project access | token verification |
| Storage signing | `roles/iam.serviceAccountTokenCreator` on `creator-studio-api@habeas-codus.iam.gserviceaccount.com` | see 2.3 |

Check that ADC works and can see the project:

```bash
gcloud auth application-default print-access-token >/dev/null && echo "ADC OK"
gcloud projects describe habeas-codus
```

### 2.3 Storage signing

The API mints V4 **signed upload URLs** so the browser uploads straight to GCS. Locally you
are a plain user, not a service account. So the backend asks IAM `signBlob` to sign on behalf
of `creator-studio-api@habeas-codus.iam.gserviceaccount.com`. There are two ways to satisfy this.

**Option 1: grant yourself signBlob.** Ask a project owner to run:

```bash
gcloud iam service-accounts add-iam-policy-binding \
  creator-studio-api@habeas-codus.iam.gserviceaccount.com \
  --member="user:YOUR_EMAIL@example.com" \
  --role="roles/iam.serviceAccountTokenCreator" \
  --project=habeas-codus
```

**Option 2: impersonate while logging in for ADC:**

```bash
gcloud auth application-default login \
  --impersonate-service-account=creator-studio-api@habeas-codus.iam.gserviceaccount.com
```

Without this, everything works except new video uploads, which fail with
`Cannot sign Cloud Storage URLs`. To use a different signing account, set
`STORAGE_SIGNING_SERVICE_ACCOUNT=` in `backend/.env`.

---

## Part 3: Environment files

### 3.1 Backend: `backend/.env`

```bash
cd backend
cp .env.example .env
```

The committed `.env.example` already works for local use against `habeas-codus`. These
defaults are worth knowing:

```dotenv
ENVIRONMENT=local
PROJECT_ID=habeas-codus
REGION=us-central1
FIREBASE_PROJECT_ID=habeas-codus
MEDIA_BUCKET=habeas-codus-media
CORPUS_BUCKET=habeas-codus-corpus
VERTEX_LOCATION=global          # cheapest Gemini endpoint
MODEL_REVIEWER=gemini-3.1-flash-lite
MODEL_ORCHESTRATOR=gemini-3.1-flash-lite
MODEL_WRITER=gemini-3.1-flash-lite
MODEL_TRANSCRIPT_REPAIR=gemini-3.1-flash-lite
MODEL_STT=chirp_3
STT_REGION=us                   # Chirp 3 is GA in the `us` multi-region, not us-central1
REVIEW_VISUAL_TOOLS_ENABLED=true
FFMPEG_PATH=ffmpeg
FFPROBE_PATH=ffprobe
```

Notes:

- **There is no LLM API key.** A stale comment in `.env.example` mentions `GEMINI_API_KEY`
  and AI Studio. Ignore it. `backend/app/providers/llm.py` builds
  `genai.Client(vertexai=True, project=..., location=...)` and authenticates with ADC. No
  key is read anywhere.
- Without FFmpeg, set `REVIEW_VISUAL_TOOLS_ENABLED=false`. Caption burn-in will then be
  unavailable, but transcription and analysis still run.
- If `backend/.env` predates the newer keys (`MODEL_WRITER`, `MODEL_TRANSCRIPT_REPAIR`,
  `REVIEW_VISUAL_TOOLS_ENABLED` and others), it still boots. Every one of them has a default
  in `backend/app/config.py`. Add the keys only if you want to change them.
- To target your own project (Track B), set `PROJECT_ID`, `FIREBASE_PROJECT_ID`,
  `MEDIA_BUCKET` and `CORPUS_BUCKET` to your names.

### 3.2 Web: `web/.env.local`

```bash
cd web
cp .env.example .env.local
```

`web/.env.example` already contains the public Firebase web config for the shared
`habeas-codus` Firebase project, plus:

```dotenv
NEXT_PUBLIC_API_BASE_URL=http://localhost:8080/api
# NEXT_PUBLIC_WS_BASE_URL=...   # leave unset in dev; derived from the API base
```

- The Firebase values are public. The API key is an identifier, not a secret, so they are
  safe to commit.
- `NEXT_PUBLIC_API_BASE_URL` is normalized in `web/src/lib/api-base.ts`. Both forms work,
  with or without the `/api` suffix.
- In dev the WebSocket is derived as `ws://localhost:8080/api/ws`. Set
  `NEXT_PUBLIC_WS_BASE_URL` only when pointing at a deployed Cloud Run URL.
- `NEXT_PUBLIC_MOCK_MODE` is not used anywhere in `web/src`. Ignore it.
- For Track B, replace all `NEXT_PUBLIC_FIREBASE_*` values with your own Firebase web app config.

---

## Part 4: Install dependencies and run

You need two terminals.

### Terminal 1: backend

```bash
cd backend
uv sync                       # creates .venv, installs Python 3.12 (from .python-version) and deps
uv run uvicorn app.main:app --reload --port 8080
```

- `uv` reads `.python-version` (`3.12`) and downloads that interpreter automatically. You do
  not need Python 3.12 on `PATH`.
- API: <http://localhost:8080>. Interactive docs are available in local mode only, at
  <http://localhost:8080/docs>.
- Health: `GET http://localhost:8080/api/healthz` and `/api/readyz`.
- Startup does not connect to GCP eagerly. The app boots even with wrong credentials, and
  the first request that touches GCP is where failures appear.

### Terminal 2: web

```bash
cd web
bun install
bun dev
```

- Open <http://localhost:3000>.
- Sign in with Google. The first time, an onboarding flow runs. After that you can create a
  project and upload a video. Test files live in `fixtures/media/` (for example
  `career_advice.mp4`, `hindi_education.mp4`, `cooking_recipe.mp4`). `fixtures/media` is
  gitignored, so if the folder is empty, get the sample videos from a teammate.

### Lint and typecheck

This project has no tests, by rule.

Backend:

```bash
cd backend
uv run ruff check .
uv run mypy app
```

Web:

```bash
cd web
bun run lint          # oxlint
bun run lint:eslint   # Next eslint config
bun run build         # static export to web/out
bun run format        # oxfmt
```

> Do not add tests, and do not run `pytest`. It is not a dependency. If you find tests,
> delete them.

---

## Part 5: Track B, create your own GCP project

Only do this if you are not using the shared `habeas-codus` project. There is no one-command
bootstrap. Terraform assumes some pieces already exist.

### 5.1 Manual console steps

1. **Create the GCP project** and link a billing account.
2. **Create the Terraform state bucket** `YOUR_PROJECT-terraform-state` (versioned, uniform
   access). `infra/backend.tf` expects it. It must exist before `terraform init`, because
   Terraform stores state there.
3. **Create the Terraform impersonation service account**
   `terraform@YOUR_PROJECT.iam.gserviceaccount.com` and grant it Owner. The alternative is the
   union of roles that `infra/iam.tf` needs: Compute, Storage, Firestore, Pub/Sub, BigQuery,
   KMS, Secret Manager, Cloud Functions, Service Usage, Service Account Admin and Billing.
   Grant your user `roles/iam.serviceAccountTokenCreator` on that account, because
   `infra/providers.tf` impersonates it.
4. **Enable Firebase** on the project in the Firebase console (import an existing GCP
   project). Accept the Firebase ToS in the console. This step cannot be automated.
5. **Enable Google sign-in** in Firebase Auth. Add `localhost` and your hosting domains under
   **Authentication → Settings → Authorized domains**.
6. **Register a Web app** in Firebase (Project settings → Your apps → Web) and copy the config
   values into `web/.env.local`.
7. **Enable the required APIs.** `services.tf` does this for you. If you apply by hand, enable:
   Storage, Firestore, Pub/Sub, BigQuery, Cloud Run, Artifact Registry, Cloud Build, Vertex AI,
   Speech-to-Text, Translation, Secret Manager, Cloud KMS, Cloud Scheduler, Firebase and
   Identity Toolkit.
8. **Vertex AI model access.** Make sure the Gemini models set in `.env` are callable from the
   project. The Agent Platform spend cap is console-only, so set it below your budget.

### 5.2 Terraform

```bash
cd infra
cp terraform.tfvars.example terraform.tfvars   # if it exists; otherwise create it
terraform init
terraform plan
terraform apply
```

Set at least these values in `terraform.tfvars`. See `infra/variables.tf` for the full set:

```hcl
project_id               = "YOUR_PROJECT_ID"
terraform_service_account = "terraform@YOUR_PROJECT_ID.iam.gserviceaccount.com"
engineer_emails          = ["you@example.com"]
billing_account_id       = "YOUR-BILLING-ACCOUNT-ID"
budget_currency          = "USD"
budget_amount            = "100"
```

> The defaults in `variables.tf` point at the shared `habeas-codus` project, the shared
> billing account and the shared engineer emails. Always override `project_id`,
> `terraform_service_account`, `engineer_emails`, `billing_account_id` and `github_repository`
> for your own project. Also update the two hardcoded names: the state bucket in
> `infra/backend.tf`, and the budget and kill-switch expectations, before you apply.

Terraform provisions the buckets, Firestore database, composite index, rules release, Pub/Sub
topics and subscriptions, BigQuery datasets, KMS keyring, empty secrets, service accounts and
IAM, Artifact Registry, the budget and the kill switch. The resource inventory is in
`infra/RESOURCES.md`.

Terraform has historically not applied one thing: the Firestore rules and index. The local ADC
lacked `firebaserules.rulesets.create`. If needed, apply them manually:

```bash
# composite index required by GET /projects
gcloud firestore indexes composite create \
  --project=YOUR_PROJECT_ID --database="(default)" --collection-group=projects \
  --query-scope=collection \
  --field-config=field-path=ownerUid,order=ascending \
  --field-config=field-path=updatedAt,order=descending

# Firestore security rules (deny all direct client access; the backend uses the Admin SDK)
firebase deploy --only firestore:rules --project YOUR_PROJECT_ID
```

### 5.3 Point the app at your project

Update `backend/.env` (`PROJECT_ID`, `FIREBASE_PROJECT_ID`, `MEDIA_BUCKET`, `CORPUS_BUCKET`) and
`web/.env.local` (all `NEXT_PUBLIC_FIREBASE_*` values and `NEXT_PUBLIC_API_BASE_URL`). Then
re-run `gcloud auth application-default set-quota-project YOUR_PROJECT_ID`.

---

## Part 6: Verify end to end

1. **Backend health**

   ```bash
   curl -s http://localhost:8080/api/healthz        # {"status":"ok"}
   ```

2. **Auth and project CRUD.** Open <http://localhost:3000>, sign in with Google, finish
   onboarding and create a project. If the project list stays empty after you create one, the
   `projects` composite index is probably missing. Firestore returns a link to create it in
   the error.
3. **Upload and transcribe.** Upload a file from `fixtures/media/`. The browser should PUT
   directly to the signed GCS URL (watch the Network tab). The API then runs STT in the
   background, and the workspace polls and shows the transcript when it is ready. Transcription
   takes seconds to minutes, depending on length. If uploads fail, see
   [2.3](#23-storage-signing).
4. **Analysis and heatmap.** Run the multi-reviewer analysis from the project view. It calls
   Gemini through Vertex AI in the background and then paints the heatmap. Watch the cost.
5. **Draft and chat.** Exercise the draft studio, which also uses the Gemini provider.

Useful log lines to watch in the backend terminal: `LLM via Agent Platform project=...` and
`LLM call model=... tools=... grounding=...`.

---

## Part 7: Manual checklist

- [ ] Install `gcloud`, `uv`, `bun`, Git and, recommended, FFmpeg.
- [ ] Run `gcloud auth login` and `gcloud auth application-default login`. ADC is the one the
      app uses.
- [ ] Run `gcloud auth application-default set-quota-project habeas-codus`.
- [ ] Get IAM access on the project: Firestore, Storage, Vertex AI, Speech-to-Text, Pub/Sub,
      and `serviceAccountTokenCreator` on the API service account (needed to sign upload URLs).
- [ ] `cp backend/.env.example backend/.env`.
- [ ] `cp web/.env.example web/.env.local` (or paste your own Firebase config).
- [ ] `cd backend && uv sync`.
- [ ] `cd web && bun install`.
- [ ] Run the backend on `:8080` and the web app on `:3000` in two terminals.
- [ ] Sign in with Google and confirm `localhost` is an Authorized Domain in Firebase Auth.
- [ ] Get the sample videos into `fixtures/media/` (gitignored).
- [ ] *(Track B only)* Create the project, state bucket and Terraform service account, enable
      Firebase, accept the ToS in the console, enable Google sign-in, register a web app, run
      `terraform apply`, apply the Firestore index and rules, and update both env files.
- [ ] *(YouTube publishing)* Create the Web OAuth client, register the redirect URI, set the
      client ID and secret (and `OAUTH_TOKEN_ENCRYPTION_KEY` locally), and add yourself as a
      test user. See Part 7b.

---

## Part 7b: YouTube connector and publishing

The studio can publish a finished project (video, thumbnail and captions) to a YouTube
channel. This needs a **Google OAuth client**. Everything else is already wired.

### 7b.1 Create the OAuth client (console only)

1. Google Cloud Console → **APIs & Services → OAuth consent screen**. Choose **External**,
   fill in the app name and support email, and add the scopes the app requests: YouTube
   upload, readonly and force-ssl, plus `yt-analytics.readonly` and email. While the app is in
   **Testing**, add every Google account you will connect as a **test user**.
2. **APIs & Services → Credentials → Create credentials → OAuth client ID → Web application**.
3. Add these **Authorized redirect URIs**:
   - Local: `http://localhost:8080/api/connections/youtube/oauth/callback`
   - Deployed: `https://creator-studio-api-3sim77rugq-uc.a.run.app/api/connections/youtube/oauth/callback`
4. Copy the **client ID** and **client secret**.

### 7b.2 Wire the credentials

Local (`backend/.env`):

```bash
GOOGLE_OAUTH_CLIENT_ID=...apps.googleusercontent.com
GOOGLE_OAUTH_CLIENT_SECRET=...
WEB_BASE_URL=http://localhost:3000
API_PUBLIC_BASE_URL=http://localhost:8080
# Encrypts OAuth tokens without Cloud KMS (local only).
OAUTH_TOKEN_ENCRYPTION_KEY=local-dev-token-key
```

Deployed: put the ID and secret in Secret Manager (`youtube-oauth-client-id` and
`youtube-oauth-client-secret`). The deploy workflow reads them into Cloud Run. Production uses
**Cloud KMS** (`user-token-key`) and must not set `OAUTH_TOKEN_ENCRYPTION_KEY`.

```bash
printf '%s' '<client-id>'     | gcloud secrets versions add youtube-oauth-client-id     --data-file=-
printf '%s' '<client-secret>' | gcloud secrets versions add youtube-oauth-client-secret --data-file=-
```

Apply the Firestore collection-group index that the OAuth callback uses:

```bash
cd infra && terraform apply   # or: gcloud firestore fields ... see firestore_indexes.tf
```

### 7b.3 How to test

1. Run the backend (`:8080`) and the web app (`:3000`).
2. Go to **Profile → Connected channels → Connect a Google account**. Google shows its account
   chooser. Pick the Gmail account that owns the channel. Every channel under it becomes a
   connection.
3. Open a video project and go to the **Publish to YouTube** module. Choose the channel, video,
   thumbnail (optional), captions, title, description, tags and visibility. Click **Publish**.
4. Watch the publish history card move from queued to uploading (with progress) to YouTube
   processing to published, with an "Open on YouTube" link.

> **Unverified API client.** Until the OAuth app passes YouTube's API audit, every upload is
> locked to **private**, whatever visibility you request. This is expected. Use a test channel.

---

## Part 8: Troubleshooting

| Symptom | Likely cause and fix |
|---|---|
| `Could not automatically determine credentials` / `DefaultCredentialsError` | You skipped `gcloud auth application-default login`, or set the wrong quota project. |
| `Cannot sign Cloud Storage URLs` on upload | `serviceAccountTokenCreator` is missing on `creator-studio-api@…`. See 2.3. |
| Upload PUT to GCS returns 403 or a CORS error | The bucket CORS config must include exactly `http://localhost:3000`. Terraform's `storage.tf` sets this. |
| Transcription request returns `403` | Missing `roles/speech.client` or `serviceusage.serviceUsageConsumer`, or the wrong region. STT must use `us` (Chirp 3), not `us-central1`. |
| LLM returns `403` or `404` for a model | Missing `roles/aiplatform.user`, the API is not enabled, or the Gemini model ID is not available in the project or region. `VERTEX_LOCATION=global`. |
| Project list empty, or 500 | Missing Firestore composite index on `projects` (`ownerUid` ASC, `updatedAt` DESC). |
| Analysis fails and mentions FFmpeg | Install FFmpeg, or set `REVIEW_VISUAL_TOOLS_ENABLED=false`. |
| Tests or `pytest` | The project has a no-tests rule. Use `ruff` and `mypy` for the backend, and `bun run lint` for the web app. |
| Stray `node_modules` or lockfile at the repo root | You ran `bun` outside `web/`. Delete the root `node_modules` and lockfile, and run Bun only inside `web/`. |
| Stale data in the UI | Firebase Hosting caches rewrite responses in production. Locally you hit the API directly. Check that `Cache-Control: no-store` is present. |

### Region and model facts (do not change casually)

- Everything is `us-central1` except Speech-to-Text, which uses the `us` multi-region
  (`STT_REGION=us`) because `chirp_3` is GA there. Do not use `us-east1`.
- The local model tier is `gemini-3.1-flash-lite` (cheap). Deployed uses `gemini-3.8-flash`
  (`backend/.env.deploy.example`).
- Paid calls (Veo at about $0.15–0.40/sec, Imagen, Gemini Pro) are capped by
  `MAX_PROJECT_COST_USD` and the project budget and kill switch. Never call them in a loop
  without a bound.

---

## Part 9: Quick reference

```bash
# ---- once ----
gcloud auth login
gcloud auth application-default login
gcloud auth application-default set-quota-project habeas-codus

cp backend/.env.example backend/.env
cp web/.env.example web/.env.local

# ---- backend ----
cd backend && uv sync
uv run uvicorn app.main:app --reload --port 8080
# checks: uv run ruff check .   |   uv run mypy app

# ---- web ----
cd web && bun install
bun dev                                   # http://localhost:3000
# checks: bun run lint | bun run lint:eslint | bun run build | bun run format

# ---- infra (Track B) ----
cd infra && terraform init && terraform plan && terraform apply
```

Open <http://localhost:3000>, sign in with Google, create a project, and upload a video from
`fixtures/media/`.
