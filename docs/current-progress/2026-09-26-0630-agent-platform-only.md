# Progress — 2026-09-26 06:30 UTC — Agent Platform only, local/deployed model configs

Supersedes `2026-09-26-0617-llm-backend-switch.md`. The Gemini Developer API (AI Studio)
backend is removed entirely; every LLM call now goes through Gemini Enterprise Agent Platform
(formerly Vertex AI). Local and deployed use different model tiers.

## Decisions

- **Drop the Developer API / Gemma path.** `GEMINI_API_KEY` and `LLM_BACKEND` are gone. The
  provider always builds `genai.Client(vertexai=True, project=..., location=...)` and uses ADC.
- **Two model configs.** Local (`backend/.env.example`) = `gemini-3.1-flash-lite` (cheap,
  ~$0.025/analysis). Deployed (`backend/.env.deploy.example`) = `gemini-3.8-flash` (stronger,
  ~$0.064/analysis at intro pricing).
- **Model choice rationale** (from the Agent Platform pricing page): flash-lite is the value
  tier; 3.1 Flash-Lite is current-gen with native structured output and long context, ~2.6x
  cheaper than Flash and ~8x cheaper than Pro. Cheaper still: Gemini 2.5 Flash Lite
  ($0.10/$0.40) but a generation older; Gemma 4 26B ($0.15/$0.60) if ever needed.
  `gemini-3.8-flash` is the quality pick while intro pricing ($0.75/$3.75) lasts — it doubles
  to $1.50/$7.50 on 2027-01-01, so prices are env-driven and must be updated then.

## What changed

- `backend/app/config.py`: removed `llm_backend` + `gemini_api_key` + the `Literal` import;
  kept `vertex_location`; model defaults now `gemini-3.1-flash-lite`; prices default
  `0.25 / 1.50`.
- `backend/app/providers/llm.py`: `_client()` always builds the Agent Platform client; no key
  check. Retry + `response_schema` unchanged.
- `backend/tests/test_providers.py`: dropped the two Developer-API tests; the Agent-Platform
  client-construction test now covers the default path.
- `backend/.env.example`: local config (Vertex + flash-lite + prices), `GEMINI_API_KEY` /
  `LLM_BACKEND` removed.
- **New `backend/.env.deploy.example`**: deployed config (Vertex + `gemini-3.8-flash` +
  `0.75 / 3.75` + Pub/Sub push vars).
- Docs: `backend-plan.md`, `backend/README.md`, `AGENTS.md`, `diagrams.md` updated to say
  Agent Platform (Vertex AI) instead of the Gemini Developer API.
- `.github/workflows/deploy.yml`: the Cloud Run deploy step now sets `VERTEX_LOCATION=global`
  and the deployed model config (`gemini-3.8-flash` + `0.75 / 3.75` prices, overridable via
  repo vars `MODEL_REVIEWER` / `MODEL_ORCHESTRATOR` / `LLM_*_PRICE_PER_MTOK`), and no longer
  mounts the `GEMINI_API_KEY` secret. That secret still exists in Secret Manager but is now
  unused (it was created manually, not via Terraform).

## Local env action required

`backend/.env` still sets `MODEL_REVIEWER` / `MODEL_ORCHESTRATOR` and `GEMINI_API_KEY`. Those
keys override defaults, so they must be changed or local calls will target a non-Vertex model:
remove `GEMINI_API_KEY` and any `LLM_BACKEND`, set `MODEL_REVIEWER` / `MODEL_ORCHESTRATOR` to
`gemini-3.1-flash-lite`, add `VERTEX_LOCATION=global` and the two price vars. Also run
`gcloud auth application-default login` + `set-quota-project habeas-codus` once.

## Verified

- Backend: `pytest` **271 passed**, `ruff` clean, `mypy` clean.
- **Live smoke tests on Vertex** via the real provider: `gemini-3.8-flash` (deployed choice)
  returned schema-valid JSON; `gemini-3.1-flash-lite` (local choice) returned schema-valid JSON
  with only 19 output tokens (no thinking tokens → genuinely cheap).

## Not done / next step

- Confirm the deploy workflow run succeeds and the API comes up with `LLM_BACKEND` gone /
  `MODEL_REVIEWER=gemini-3.8-flash`; the runtime SA already has the Vertex AI role and
  `aiplatform.googleapis.com` is enabled.
- Run one real analysis end to end on `fixtures/media/` with the new defaults.
- Optional cost lever: batch/flex is 50% off if analysis can move to the Batch API.
- Optional cleanup: delete the unused `gemini-api-key` Secret Manager secret.
