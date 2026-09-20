# Progress — 2026-09-20 19:10 IST

Status: **minimal deploy pipeline implemented and infra prerequisites applied. Push to `main`
deploys the API and web app to Cloud Run.**

## 1. What I did

Replaced the earlier over-engineered plan with the minimum needed to deploy.

- `.github/workflows/deploy.yml` — on push to `main` (and manual dispatch): builds `api` and `web`
  images, pushes to Artifact Registry, deploys both to Cloud Run. Runs on a Blacksmith runner,
  authenticates with Workload Identity Federation (no keys).
- `web/Dockerfile` + `web/.dockerignore` — Next.js standalone container (Bun build → node runtime,
  non-root).
- `web/next.config.ts` — `output: "standalone"`.
- `backend/Dockerfile` — runs as non-root (`uid 10001`).
- `backend/app/main.py` — `/openapi.json` disabled outside local (with `/docs`).
- `infra/wif.tf`, `infra/variables.tf`, `infra/iam.tf`, `infra/service_accounts.tf`,
  `infra/outputs.tf` — WIF pool/provider, deployer `iam.serviceAccountUser`, `creator-studio-web`
  SA, outputs for the repo variables.

## 2. Infra applied

- Granted the Terraform SA `roles/iam.workloadIdentityPoolAdmin` (it was missing).
- `terraform apply -target=...` created the WIF pool/provider and `creator-studio-web`; the deployer
  already had `roles/iam.workloadIdentityUser` and `roles/iam.serviceAccountUser`.
- GitHub repo variables set: `GCP_WIF_PROVIDER`, `GCP_DEPLOY_SA`.

## 3. Gotchas

- A full `terraform apply` currently fails on **pre-existing drift**: the `projects` composite index
  exists but is not in state (`409 already exists`), and the Terraform SA lacks
  `firebaserules.rulesets.create`. Both predate this work and are unrelated to deploying. Use a
  targeted apply (or fix the drift) until they are imported/granted.
- The Terraform SA lacked `iam.workloadIdentityPoolAdmin`; now granted.
- Two-pass config: the web image bakes `NEXT_PUBLIC_API_BASE_URL` at build time and the API bakes
  `CORS_ALLOWED_ORIGINS`. Until `API_URL` / `CORS_ALLOWED_ORIGINS` repo variables are set and the
  workflow re-run, the deployed web app will not reach the API.

## 4. Deliberately not done

Rate limiting, ID-token revocation check, API-key referrer restriction, deny-all Firebase Storage
rules, Firestore delete protection / TTL, and a PR verify workflow. Deferred to keep the first
deploy small.

## 5. Next step

1. Confirm the Blacksmith GitHub App is installed (or change `runs-on` to `ubuntu-latest`).
2. Push to `main`; wait for the deploy run.
3. Read the API URL, set repo variables `API_URL` and `CORS_ALLOWED_ORIGINS`
   (`["https://<web-url>","https://habeas-codus.web.app"]`), re-run the workflow.
4. Smoke test: `/healthz`, and sign in through the deployed web app.
