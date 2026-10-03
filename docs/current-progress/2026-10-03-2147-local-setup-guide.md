# Local setup guide

## What I did

Wrote `LOCAL_SETUP.md` at the repo root: an end-to-end guide for running web + backend locally
against the real GCP project. Covers tooling (gcloud/uv/bun/ffmpeg/terraform), ADC login and IAM,
Storage V4 signing, backend/env config, running both dev servers, manual GCP/Firebase steps, a
Track B (own-project + Terraform) path, an end-to-end verification flow, a manual checklist, and
a troubleshooting table.

## What changed structurally

None (docs only). No contracts, schema, or infra changes. `LOCAL_SETUP.md` is untracked and was
not committed, per request.

## Discoveries / gotchas worth recording

- `backend/.env.example` has a stale comment claiming `GEMINI_API_KEY` / AI Studio is the LLM
  backend. It is not: `providers/llm.py` uses `genai.Client(vertexai=True, ...)` with ADC only.
  The guide calls this out so a new dev does not chase a non-existent key.
- Local uploads require `roles/iam.serviceAccountTokenCreator` on
  `creator-studio-api@habeas-codus.iam.gserviceaccount.com` (or ADC impersonation), otherwise
  V4 signed URL minting fails.
- `web/.env.local`'s `NEXT_PUBLIC_MOCK_MODE=off` is unused in `web/src`; there is no mock mode.
- Workers run in-process via FastAPI `BackgroundTasks`; Pub/Sub publishes are best-effort, so no
  separate worker or Pub/Sub push endpoint is needed locally.

## Not done / next step

- Not verified by running the app end to end (this was a docs task). Next step: follow the guide
  on a clean machine and fix anything that drifts.
- If the stale `.env.example` comment should be corrected in code/docs, that is a follow-up.
