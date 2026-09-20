# Progress — 2026-09-20 20:05 IST

Status: **deployed and verified on stable URLs. Push to `main` deploys the API (Cloud Run) and the
web app (Firebase Hosting).**

## 0. Deployed URLs

- **Web (share this): https://habeas-codus.web.app**
- **API (same origin): https://habeas-codus.web.app/api/...** — Firebase Hosting rewrites `/api/**`
  to the `creator-studio-api` Cloud Run service, so there is no separate API URL and no CORS in
  production. The raw `*.run.app` URL still exists but is internal only.
- GitHub repo variables: `GCP_WIF_PROVIDER`, `GCP_DEPLOY_SA`, `API_URL`
  (`https://habeas-codus.web.app/api`), `CORS_ALLOWED_ORIGINS`.

## 1. What changed

- **Web is now a static Next.js export served by Firebase Hosting**, not a Cloud Run container.
  `web/next.config.ts` uses `output: "export"` + `images.unoptimized`; `firebase.json` has a
  `hosting` block (`public: web/out`, `cleanUrls`). This gives the stable `habeas-codus.web.app`
  domain and removes the web Cloud Run service (deleted).
- `.github/workflows/deploy.yml` — one job on `ubuntu-latest`: build+push the API image and deploy
  `creator-studio-api`; then build the web static export and `firebase deploy --only hosting`. WIF
  auth, no keys.
- `backend/Dockerfile` non-root; `backend/app/main.py` hides `/openapi.json` outside local.
- `infra/wif.tf` etc. — WIF pool/provider; deployer has `roles/run.admin` (to set public invoker),
  `roles/iam.serviceAccountUser`, and `roles/firebasehosting.admin`.

## 2. Infra applied

- Terraform SA granted `roles/iam.workloadIdentityPoolAdmin`; deployer granted `run.admin` and
  `firebasehosting.admin` (targeted applies).
- WIF pool/provider + `allUsers` invoker on `creator-studio-api`; `creator-studio-web` Cloud Run
  service deleted.

## 3. Verification

- `https://habeas-codus.web.app/` → 200; `/dashboard` → 200 (cleanUrls); title renders.
- `/readyz` → 200; `/projects`, `/me` without a token → 401; `/openapi.json` → 404; CORS preflight
  from `https://habeas-codus.web.app` is allowed.

## 4. Gotchas

- **`/healthz` is reserved by Google's front end on Cloud Run** — it 404s at the edge and never
  reaches the container. Use `/readyz`.
- `NEXT_PUBLIC_*` values are baked at build time, so the web build needs `NEXT_PUBLIC_API_BASE_URL`
  and the API needs `CORS_ALLOWED_ORIGINS`; both are repo variables consumed by the workflow.
- A full `terraform apply` still fails on pre-existing drift (the `projects` composite index is not
  in state; the Terraform SA lacks `firebaserules.rulesets.create`). Use targeted applies until
  fixed.

## 5. Deliberately not done

Rate limiting, ID-token revocation check, API-key referrer restriction, deny-all Firebase Storage
rules, Firestore delete protection / TTL, PR verify workflow.

## 6. Next step

- Sign in through https://habeas-codus.web.app with a real Google account to confirm the
  Firebase auth → API round trip.
