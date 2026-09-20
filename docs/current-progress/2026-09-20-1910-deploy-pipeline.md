# Progress — 2026-09-20 19:10 IST

Status: **deployed and verified. Push to `main` deploys the API and web app to Cloud Run.**

## 0. Deployed URLs

- Web: https://creator-studio-web-3sim77rugq-uc.a.run.app
- API: https://creator-studio-api-3sim77rugq-uc.a.run.app
- GitHub repo variables set: `GCP_WIF_PROVIDER`, `GCP_DEPLOY_SA`, `API_URL`, `CORS_ALLOWED_ORIGINS`.

## 1. What I did

Replaced the earlier over-engineered plan with the minimum needed to deploy.

- `.github/workflows/deploy.yml` — on push to `main` (and manual dispatch): builds `api` and `web`
  images, pushes to Artifact Registry, deploys both to Cloud Run. Runs on GitHub-hosted
  `ubuntu-latest`, authenticates with Workload Identity Federation (no keys).
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
- Granted the deployer `roles/run.admin` (was `run.developer`), so `gcloud run deploy
  --allow-unauthenticated` can actually set the public invoker binding. Without it the deploy
  printed `Setting IAM Policy ... warning` and the services stayed private.
- GitHub repo variables set: `GCP_WIF_PROVIDER`, `GCP_DEPLOY_SA`, `API_URL`, `CORS_ALLOWED_ORIGINS`.

## 3. Verification

- `GET /readyz` → 200; `GET /projects` and `/me` without a token → 401; `GET /openapi.json` → 404
  (prod); web root → 200; CORS preflight from the web origin returns the right
  `access-control-allow-origin`; `allUsers` is bound to `roles/run.invoker` on both services.

## 4. Gotchas

- **`/healthz` is reserved by Google's front end on Cloud Run.** Requests to it return Google's
  generic 404 page and never reach the container. Use `/readyz` (works) for checks; not worth
  renaming the contract.
- A full `terraform apply` currently fails on **pre-existing drift**: the `projects` composite index
  exists but is not in state (`409 already exists`), and the Terraform SA lacks
  `firebaserules.rulesets.create`. Both predate this work. Use a targeted apply until the drift is
  imported/granted.
- Blacksmith was dropped — not appropriate for a personal project. The workflow uses
  GitHub-hosted `ubuntu-latest` with plain `docker build`/`docker push`.
- Two-pass config (already done): the web image bakes `NEXT_PUBLIC_API_BASE_URL` at build time and
  the API bakes `CORS_ALLOWED_ORIGINS`, so changing either requires a redeploy.

## 5. Deliberately not done

Rate limiting, ID-token revocation check, API-key referrer restriction, deny-all Firebase Storage
rules, Firestore delete protection / TTL, and a PR verify workflow. Deferred to keep the first
deploy small.

## 6. Next step

- Sign in through the deployed web app with a real Google account to confirm Firebase auth → API
  round trip.
- Add remaining security hardening (see above) if time allows.
