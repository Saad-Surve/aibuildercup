# Progress — 2026-09-20 21:20 IST

Status: **Gemini key is in Secret Manager and mounted on Cloud Run; the deploy workflow now keeps it.
Production still runs the old Vertex image until the next push.**

## 1. What I did

1. Created Secret Manager secret `gemini-api-key` (project `habeas-codus`, automatic replication)
   from the value already in `backend/.env`, piped straight into `gcloud` — the key was never read
   into the conversation or printed.
2. Granted `roles/secretmanager.secretAccessor` on the secret to:
   - runtime SA `creator-studio-api@habeas-codus.iam.gserviceaccount.com` (so the container can read it)
   - deployer SA `creator-studio-deployer@habeas-codus.iam.gserviceaccount.com` (so CI can deploy it)
3. Updated the live service: `gcloud run services update creator-studio-api --update-secrets
   GEMINI_API_KEY=gemini-api-key:latest`. `describe` confirms the env var resolves via
   `secretKeyRef`.
4. `.github/workflows/deploy.yml`: the `gcloud run deploy` step now also passes
   `--set-secrets "GEMINI_API_KEY=gemini-api-key:latest"`, so future deploys keep it.

## 2. Important: production is still on the old image

The deployed revision runs image tag `1afaa62…` (commit `1afaa62`, the pre-session HEAD). That image
is the **old Vertex-based `llm.py`** — it ignores `GEMINI_API_KEY` and calls Vertex via the service
account, using the old default `MODEL_ORCHESTRATOR=gemini-2.5-pro`. The new AI-Studio-only code plus
the `gemini-flash-latest` registry are **uncommitted**.

So the secret is mounted but inert until the pipeline deploys a new image. To activate:
commit the working tree and push to `main` (the workflow then builds/pushes/deploys and the key takes
effect). Do not commit `backend/.env` (gitignored) or any key material.

## 3. Verification

- `gcloud run services describe` shows `GEMINI_API_KEY` → `secretKeyRef: gemini-api-key:latest`.
- `https://habeas-codus.web.app/api/readyz` → 200; `/api/me` (no token) → 401.
- `deploy.yml` parses as valid YAML.
- Local previously verified: 93 tests, `ruff`/`mypy` clean, live AI Studio call succeeded.

## 4. Note

`gh secret list` is empty, so no GitHub Actions secret was added — the key lives only in Secret
Manager (correct per AGENTS.md rule 6). Nothing in the repo contains the key.

## 5. Next

Commit + push when ready (deploys the project workspace slice and the AI Studio LLM path together),
or keep building the transcribe worker locally first. Unrelated pre-existing change in the tree:
`.gitignore` gained `fixtures/media`.
