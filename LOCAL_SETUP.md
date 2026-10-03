# Local Setup & Run Guide — Habeas Codus (Creator Helper Studio)

This guide takes you from a clean machine to a running local app (`web/` talking to `backend/`)
using the **real** Google Cloud services: Gemini on Agent Platform (Vertex AI), Speech-to-Text,
Cloud Storage, Firestore, Pub/Sub and Firebase Auth.

> Read `AGENTS.md` first, then `docs/technical-design/README.md`. This guide only covers *how to
> get it running locally*.

There are two tracks:

- **Track A — Use the existing `habeas-codus` GCP project (recommended).** You only need access to
  the shared project and to log in. Fastest path; everything is already provisioned.
- **Track B — Create your own GCP project from scratch.** You get to provision Firestore, buckets,
  Pub/Sub, Firebase, etc. yourself (mostly via Terraform). Much more work; covered in
  [Part 5](#part-5--track-b-create-your-own-gcp-project-from-scratch).

---

## 0. Architecture in one paragraph (what actually runs locally)

- `web/` is a Next.js 16 static-export frontend (Bun). It signs the user in with **Firebase Auth**
  (Google provider) and calls the backend at `http://localhost:8080/api` with a Firebase ID token.
- `backend/` is FastAPI (uv). It verifies the ID token with **Firebase Admin**, then reads/writes
  **Firestore**, uploads/reads **Cloud Storage**, calls **Vertex AI** (Gemini) for reviewers /
  transcription repair / drafting, and **Speech-to-Text V2** (`chirp_3`, `us` multi-region) for
  transcription.
- **Workers run in-process locally** via FastAPI `BackgroundTasks`: on upload-complete the API runs
  the transcribe worker itself and then the analysis worker. It also *tries* to publish Pub/Sub
  events (best-effort; a publish failure is logged, not fatal). So you do **not** need to run a
  separate worker process or the Pub/Sub push endpoint locally.
- Local dev hits the **real** GCP project, so you need real credentials (Application Default
  Credentials). There is no emulator/mock mode in this repo.

---

## 1. Prerequisites (install these first)

| Tool | Version / notes | Why |
|---|---|---|
| **Google Cloud SDK (`gcloud`)** | any recent | auth + ADC + project access |
| **uv** | `>= 0.5` | backend package manager + Python 3.12 |
| **Bun** | `1.4.x` (repo pins `bun@1.4.2`) | web package manager + dev server |
| **Git** | any | clone |
| **FFmpeg + ffprobe** | on `PATH` | reviewer footage tools + caption burn-in |
| **Terraform** (Track B only) | `1.6+` | provisioning GCP |
| **Docker** (optional) | only for the deploy image | not needed to run locally |

One-liners (choose per your OS):

```bash
# gcloud — Windows (winget) / macOS (brew)
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

# FFmpeg — Windows (winget) / macOS (brew)
winget install Gyan.FFmpeg
# brew install ffmpeg

# Terraform — Windows (winget) / macOS (brew)
winget install Hashicorp.Terraform
# brew install terraform
```

Verify:

```bash
git --version
gcloud --version
uv --version
bun --version
ffmpeg -version && ffprobe -version
```

> **Don't run `npm`/`pip`/`poetry`/`yarn`.** `web/` is Bun-only, `backend/` is uv-only. This is a
> hard rule in `AGENTS.md` and stray lockfiles cause real breakage. Only run `bun` from inside
> `web/`.

---

## Part 2 — Credentials & Google access

These steps are identical for Track A and B (Track B does them against your own project).

### 2.1 Log in with your Google account

```bash
# 1. Log into gcloud with the browser (this is the "gcloud CLI" login)
gcloud auth login

# 2. Point gcloud at the project
gcloud config set project habeas-codus

# 3. Application Default Credentials — THIS is what the backend uses.
gcloud auth application-default login

# 4. Tell ADC which project to bill quota to (avoids "quota project" warnings/errors)
gcloud auth application-default set-quota-project habeas-codus
```

The backend never reads a service-account JSON file locally. Every Google SDK call
(`google.genai`, `google.cloud.storage`, `google.cloud.firestore`, `google.cloud.speech_v2`,
`firebase_admin`) uses the ADC created by step 3.

### 2.2 Confirm you actually have access

You need, on the `habeas-codus` project, at minimum **Viewer/Editor**-level access plus these
service roles on your user account:

| Service | Role your user needs | Notes |
|---|---|---|
| Firestore | `roles/datastore.user` | read/write docs |
| Cloud Storage | `roles/storage.objectAdmin` on `habeas-codus-media` (+ `-corpus`) | read/write objects |
| Vertex AI / Agent Platform | `roles/aiplatform.user` | Gemini calls |
| Speech-to-Text | `roles/speech.client` + `roles/serviceusage.serviceUsageConsumer` | `chirp_3` batch |
| Pub/Sub | `roles/pubsub.publisher` on the topics | best-effort events |
| Firebase Auth | Firebase Admin SDK is fine with project access | token verification |
| Storage signing | `roles/iam.serviceAccountTokenCreator` **on `creator-studio-api@habeas-codus.iam.gserviceaccount.com`** | see 2.3 |

Quick check that ADC works and can see the project:

```bash
gcloud auth application-default print-access-token >/dev/null && echo "ADC OK"
gcloud projects describe habeas-codus
```

### 2.3 Storage signing (the one that bites people)

The API mints V4 **signed upload URLs** so the browser uploads straight to GCS. Locally you are a
plain user (not a service account), so the backend asks IAM `signBlob` to sign on behalf of
`creator-studio-api@habeas-codus.iam.gserviceaccount.com`. Two ways to satisfy it:

**Option 1 (grant yourself signBlob):** ask a project owner to run

```bash
gcloud iam service-accounts add-iam-policy-binding \
  creator-studio-api@habeas-codus.iam.gserviceaccount.com \
  --member="user:YOUR_EMAIL@example.com" \
  --role="roles/iam.serviceAccountTokenCreator" \
  --project=habeas-codus
```

**Option 2 (impersonate while logging in as ADC):**

```bash
gcloud auth application-default login \
  --impersonate-service-account=creator-studio-api@habeas-codus.iam.gserviceaccount.com
```

If you skip this, everything works **except** new video uploads, which fail with
`Cannot sign Cloud Storage URLs`. Override the account with
`STORAGE_SIGNING_SERVICE_ACCOUNT=` in `backend/.env` if you use a different one.

---

## Part 3 — Configure the environment files

### 3.1 Backend `backend/.env`

```bash
cd backend
cp .env.example .env
```

The committed `.env.example` is already correct for local use against `habeas-codus`. Defaults
you should know:

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
STT_REGION=us                   # Chirp 3 is GA on the `us` multi-region, not us-central1
REVIEW_VISUAL_TOOLS_ENABLED=true
FFMPEG_PATH=ffmpeg
FFPROBE_PATH=ffprobe
```

Notes:

- **There is no LLM API key.** One stale comment in `.env.example` mentions `GEMINI_API_KEY` /
  AI Studio — ignore it. `backend/app/providers/llm.py` builds
  `genai.Client(vertexai=True, project=..., location=...)` and authenticates with ADC. No key is
  read anywhere.
- If you don't have FFmpeg, set `REVIEW_VISUAL_TOOLS_ENABLED=false` and caption burn-in will be
  unavailable, but transcription/analysis still run.
- If `backend/.env` already exists from a previous session, it may be missing the newer keys
  (`MODEL_WRITER`, `MODEL_TRANSCRIPT_REPAIR`, `REVIEW_VISUAL_TOOLS_ENABLED`, …). They all have
  defaults in `backend/app/config.py`, so it still boots; add them if you want to change them.
- To target your own project (Track B), set `PROJECT_ID`, `FIREBASE_PROJECT_ID`,
  `MEDIA_BUCKET`, `CORPUS_BUCKET` to your names.

### 3.2 Web `web/.env.local`

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

- The Firebase values are **public** (the API key is an identifier, not a secret). Safe to commit.
- `NEXT_PUBLIC_API_BASE_URL` is normalised in `web/src/lib/api-base.ts` — with or without the
  `/api` suffix both work.
- In dev the WebSocket is derived as `ws://localhost:8080/api/ws`; only set
  `NEXT_PUBLIC_WS_BASE_URL` when pointing at a deployed Cloud Run URL.
- `NEXT_PUBLIC_MOCK_MODE` is **not used** anywhere in `web/src` — ignore it.
- For Track B, replace all `NEXT_PUBLIC_FIREBASE_*` values with your own Firebase web app config.

---

## Part 4 — Install dependencies and run

You need **two terminals**.

### Terminal 1 — backend

```bash
cd backend
uv sync                       # creates .venv, installs Python 3.12 (from .python-version) + deps
uv run uvicorn app.main:app --reload --port 8080
```

- `uv` reads `.python-version` (`3.12`) and downloads that interpreter automatically — you do
  **not** need Python 3.12 on `PATH`.
- API: <http://localhost:8080>. Interactive docs only in local mode: <http://localhost:8080/docs>.
- Health: `GET http://localhost:8080/api/healthz` and `/api/readyz`.
- On startup the app does **not** eagerly connect to GCP, so it will boot even if credentials are
  wrong; the first request that touches GCP is where failures show up.

### Terminal 2 — web

```bash
cd web
bun install
bun dev
```

- Open <http://localhost:3000>.
- Sign in with Google. The first time, an onboarding flow runs, then you can create a project and
  upload a video. Test files live in `fixtures/media/` (e.g. `career_advice.mp4`,
  `hindi_education.mp4`, `cooking_recipe.mp4`). `fixtures/media` is gitignored, so if the folder is
  empty you need to get the sample videos from a teammate.

### Lint / typecheck (the project has **no tests** by rule)

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

> Do **not** add tests and do not run `pytest` (it isn't a dependency). If you find tests, delete
> them.

---

## Part 5 — Track B: create your own GCP project from scratch

Only if you are **not** using the shared `habeas-codus` project. There is no one-command bootstrap;
Terraform assumes some things already exist.

### 5.1 Manual (console) steps you cannot avoid

1. **Create the GCP project** and link a billing account.
2. **Create the Terraform state bucket** `YOUR_PROJECT-terraform-state` (versioned, uniform access)
   — this is what `infra/backend.tf` expects. It must exist *before* `terraform init`, because
   Terraform stores state there.
3. **Create the Terraform impersonation service account**
   `terraform@YOUR_PROJECT.iam.gserviceaccount.com` and grant it **Owner** (or the union of roles
   `infra/iam.tf` needs: Compute/Storage/Firestore/PubSub/BigQuery/KMS/Secret Manager/Cloud
   Functions/Service Usage/Service Account Admin/Billing). Grant **your user** the
   `roles/iam.serviceAccountTokenCreator` on it, because `infra/providers.tf` impersonates it.
4. **Enable Firebase** on the project in the Firebase console (import an existing GCP project).
   Accept the Firebase ToS **in the console** — this cannot be automated.
5. **Enable Google sign-in** in Firebase Auth, and add `localhost` and your hosting domains to
   **Authentication → Settings → Authorized domains**.
6. **Register a Web app** in Firebase (Project settings → Your apps → Web) and copy the config
   values into `web/.env.local`.
7. **Enable the required APIs** (Terraform `services.tf` does this, but if applying by hand:
   Storage, Firestore, Pub/Sub, BigQuery, Cloud Run, Artifact Registry, Cloud Build, Vertex AI,
   Speech-to-Text, Translation, Secret Manager, Cloud KMS, Cloud Scheduler, Firebase,
   Identity Toolkit).
8. **Vertex AI model access**: make sure the Gemini models you set in `.env` are callable from the
   project. (The Agent Platform "Spend Cap" is console-only; set it below your budget.)

### 5.2 Terraform

```bash
cd infra
cp terraform.tfvars.example terraform.tfvars   # if it exists; otherwise create it
terraform init
terraform plan
terraform apply
```

Set at least these in `terraform.tfvars` (see `infra/variables.tf` for the full set):

```hcl
project_id               = "YOUR_PROJECT_ID"
terraform_service_account = "terraform@YOUR_PROJECT_ID.iam.gserviceaccount.com"
engineer_emails          = ["you@example.com"]
billing_account_id       = "YOUR-BILLING-ACCOUNT-ID"
budget_currency          = "USD"
budget_amount            = "100"
```

> The defaults in `variables.tf` point at the shared `habeas-codus` project, the shared billing
> account, and the shared engineer emails — **always override `project_id`,
> `terraform_service_account`, `engineer_emails`, `billing_account_id`, and `github_repository`**
> for your own project. Also update the two hardcoded names: the state bucket in
> `infra/backend.tf` and the budget/killswitch expectations, before applying.

Terraform provisions the buckets, Firestore database, composite index, rules release, Pub/Sub
topics/subscriptions, BigQuery datasets, KMS keyring, empty secrets, service accounts + IAM,
Artifact Registry, the budget and the kill switch. Resource inventory: `infra/RESOURCES.md`.

The one thing Terraform historically did **not** apply (because the local ADC lacked
`firebaserules.rulesets.create`) is the Firestore rules/index. If needed, apply manually:

```bash
# composite index required by GET /projects
gcloud firestore indexes composite create \
  --project=YOUR_PROJECT_ID --database="(default)" --collection-group=projects \
  --query-scope=collection \
  --field-config=field-path=ownerUid,order=ascending \
  --field-config=field-path=updatedAt,order=descending

# Firestore security rules (deny all direct client access; backend uses Admin SDK)
firebase deploy --only firestore:rules --project YOUR_PROJECT_ID
```

### 5.3 Point the app at your project

Update `backend/.env` (`PROJECT_ID`, `FIREBASE_PROJECT_ID`, `MEDIA_BUCKET`, `CORPUS_BUCKET`) and
`web/.env.local` (all `NEXT_PUBLIC_FIREBASE_*` and `NEXT_PUBLIC_API_BASE_URL`). Then re-run
`gcloud auth application-default set-quota-project YOUR_PROJECT_ID`.

---

## Part 6 — Verify it works end to end

1. **Backend health**
   ```bash
   curl -s http://localhost:8080/api/healthz        # {"status":"ok"}
   ```
2. **Auth + project CRUD**: open <http://localhost:3000>, sign in with Google, complete onboarding,
   create a project. If the project list is empty after creating one, you're most likely missing the
   `projects` composite index (Firestore returns a link in the error).
3. **Upload + transcribe**: upload a file from `fixtures/media/`. The browser should PUT directly to
   the signed GCS URL (watch the Network tab). The API then runs STT in the background; the
   workspace polls and shows the transcript when ready. Transcription takes seconds-to-minutes
   depending on length. If uploads fail, revisit [2.3](#23-storage-signing-the-one-that-bites-people).
4. **Analysis / heatmap**: run the multi-reviewer analysis from the project view. This calls Gemini
   via Vertex AI in the background and paints the heatmap. Keep an eye on cost.
5. **Draft / chat**: exercise the draft studio, which also uses the Gemini provider.

Useful log lines to watch for in the backend terminal: `LLM via Agent Platform project=...` and
`LLM call model=... tools=... grounding=...`.

---

## Part 7 — What you must do manually (checklist)

- [ ] Install `gcloud`, `uv`, `bun`, Git, and (recommended) FFmpeg.
- [ ] `gcloud auth login` **and** `gcloud auth application-default login` (ADC is the one that
      matters).
- [ ] `gcloud auth application-default set-quota-project habeas-codus`.
- [ ] Get IAM access on the project: Firestore, Storage, Vertex AI, Speech-to-Text, Pub/Sub, and
      `serviceAccountTokenCreator` on the API service account (needed to sign upload URLs).
- [ ] `cp backend/.env.example backend/.env`.
- [ ] `cp web/.env.example web/.env.local` (or paste your own Firebase config).
- [ ] `cd backend && uv sync`.
- [ ] `cd web && bun install`.
- [ ] Run the backend on `:8080` and the web app on `:3000` (two terminals).
- [ ] Sign in with Google and confirm the Authorized Domain `localhost` is set in Firebase Auth.
- [ ] Provide/obtain the sample videos in `fixtures/media/` (gitignored).
- [ ] *(Track B only)* Create the project + state bucket + Terraform SA, enable Firebase, accept
      ToS in console, enable Google sign-in, register a web app, run `terraform apply`, apply the
      Firestore index/rules, and update both env files.

---

## Part 8 — Troubleshooting / gotchas

| Symptom | Likely cause & fix |
|---|---|
| `Could not automatically determine credentials` / `DefaultCredentialsError` | You skipped `gcloud auth application-default login`, or set it to the wrong quota project. |
| `Cannot sign Cloud Storage URLs` on upload | Missing `serviceAccountTokenCreator` on `creator-studio-api@…` — see 2.3. |
| Upload PUT to GCS returns 403/CORS | Bucket CORS must include exactly `http://localhost:3000`. Terraform `storage.tf` sets this. |
| Transcription request `403` | Missing `roles/speech.client` / `serviceusage.serviceUsageConsumer`, or wrong region. STT must use `us` (Chirp 3), not `us-central1`. |
| LLM `403`/`404` model | Missing `roles/aiplatform.user`, API not enabled, or the Gemini model id isn't available in the project/region. `VERTEX_LOCATION=global`. |
| Project list empty / 500 | Missing Firestore composite index on `projects` (`ownerUid` ASC, `updatedAt` DESC). |
| Analysis fails needing FFmpeg | Install FFmpeg, or set `REVIEW_VISUAL_TOOLS_ENABLED=false`. |
| Tests / `pytest` | The project has a no-tests rule. Use `ruff` + `mypy` (backend) and `bun run lint` (web). |
| Stray `node_modules`/lockfile at repo root | You ran `bun` outside `web/`. Delete root `node_modules` + lockfile and only run Bun inside `web/`. |
| Stale data in the UI | Firebase Hosting caches rewrite responses in prod. Locally you hit the API directly; check `Cache-Control: no-store` is present. |

### Region / model facts (do not change casually)

- Everything is `us-central1` **except** Speech-to-Text, which uses the `us` multi-region
  (`STT_REGION=us`) because `chirp_3` is GA there. Do not use `us-east1`.
- Local model tier is `gemini-3.1-flash-lite` (cheap). Deployed uses `gemini-3.8-flash`
  (`backend/.env.deploy.example`).
- Paid calls (Veo `~$0.15–0.40/sec`, Imagen, Gemini Pro) are capped by `MAX_PROJECT_COST_USD` and
  the project budget/kill switch. Never call them in a loop without a bound.

---

## Part 9 — Quick reference

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

Open <http://localhost:3000>, sign in with Google, create a project, and upload a `fixtures/media/`
video.
