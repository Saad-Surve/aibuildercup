# Progress — 2026-09-20 21:30 IST

Status: **Pushed to `main` and deployed. Production now runs the project workspace slice and the
Gemini Developer API path with the key from Secret Manager.**

## 1. Commits

- `552ff61` Add project workspace with direct video upload and jobs
- `a632159` Use a Gemini Developer API key instead of Vertex AI

Pushed `1afaa62..a632159` to `main`. Deploy workflow run `35520879394` completed successfully
(build+push API image, deploy Cloud Run, build web static export, deploy Firebase Hosting).

## 2. Verified in production

- Cloud Run image is now `api:a632159…` (was `1afaa62`).
- `GEMINI_API_KEY` still resolves via `secretKeyRef: gemini-api-key:latest` after the workflow's
  `--set-secrets`.
- `https://habeas-codus.web.app/api/readyz` → 200; `/api/me` (no token) → 401;
  `https://habeas-codus.web.app/projects` → 200.

Not verified end to end: an authenticated persona/LLM call in production (needs a signed-in
session). The same code path was verified locally against the AI Studio key.

## 3. Not committed (intentional)

- `fixtures/cassettes/llm/4c36…json` — the persona cassette recorded earlier through Vertex. It is
  keyed on `gemini-2.5-pro`, so it can never match under the new model, and it embeds a persona from
  real onboarding answers. Left untracked; delete it when convenient.
- `backend/.env`, `web/.env`, `fixtures/media/` — gitignored. No secret material is in the repo.

## 4. Next step

Test the deployed flow: sign in, complete onboarding (persona should now come from the free Gemini
flash model), create a project, upload a video. The upload will queue a `transcribe` job that nothing
consumes yet — the transcribe worker + STT provider is the next build.
