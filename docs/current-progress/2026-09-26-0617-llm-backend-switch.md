# Progress — 2026-09-26 06:17 UTC — LLM backend switch (Gemma local, Vertex deployed)

Adds a switchable LLM backend so local development stays on free Gemma and only the
deployed service spends GCP budget on Agent Platform (formerly Vertex AI) Gemini.

## What changed

- `backend/app/config.py`
  - New `llm_backend: Literal["developer", "vertex"] = "developer"` — `developer` is the
    Gemini Developer API (AI Studio, `GEMINI_API_KEY`, free); `vertex` is Gemini Enterprise
    Agent Platform, authenticated with ADC against `project_id` / `vertex_location`.
  - New `vertex_location: str = "global"` (cheapest Gemini endpoint; not tied to `region`).
  - Model registry defaults stay Gemma 4 (free); the deployed `vertex` service overrides
    `MODEL_REVIEWER` / `MODEL_ORCHESTRATOR` with Gemini ids via env.
- `backend/app/providers/llm.py`
  - Extracted `_client()`, which branches on `llm_backend`: `genai.Client(api_key=...)` for
    `developer`, `genai.Client(vertexai=True, project=..., location=...)` for `vertex`.
  - Shared retry loop and `response_schema` config are unchanged — Vertex supports the same
    controlled-generation config the provider already sends.
  - Error message now names both backends.
- `backend/tests/test_providers.py`: new test asserts the vertex path constructs the client
  with `vertexai=True` + project + location and needs no API key.
- `backend/.env.example`: added `LLM_BACKEND`, `VERTEX_LOCATION`; clarified model comments.
- `docs/technical-design/backend-plan.md` and `backend/README.md`: documented the switch.

No contract, schema, or IAM change. The API runtime SA already has the Vertex AI role
(`infra/RESOURCES.md:136`), and `aiplatform.googleapis.com` is already enabled on the project.

## Deploy-time env (Cloud Run is deployed manually, not via Terraform)

Set these on the deployed API service only:

```
LLM_BACKEND=vertex
VERTEX_LOCATION=global
MODEL_REVIEWER=gemini-<flash-class>        # e.g. gemini-3.8-flash (intro price to 2026-12-31)
MODEL_ORCHESTRATOR=gemini-<flash-class>
LLM_INPUT_PRICE_PER_MTOK=0.75              # Vertex Gemini is NOT free; costs are understated at 0
LLM_OUTPUT_PRICE_PER_MTOK=3.75
```

`GEMINI_API_KEY` is only needed by the `developer` backend; the `vertex` backend uses the
Cloud Run runtime service account's ADC.

## Safety

- Vertex spend is covered by the $300 trial credit **only via Agent Platform**, not the AI
  Studio Gemini API (see the 2026-09-26 Gemma note). A project+service **Spend Cap** should be
  set below the project-wide budget so Vertex pauses before the `budget-killswitch` detaches
  billing. Spend caps are console-only (no Terraform) for now.
- Killswitch (`infra/budget.tf`, `infra/killswitch/main.py`) is unchanged and remains the
  project-wide backstop.

## Verified

- Backend: `pytest` **273 passed** (new vertex test), `ruff` clean, `mypy` clean.
- **Live Vertex smoke test passed** (2026-09-26, after the spend cap was set): one
  `gemini-3.8-flash` call through the real `LlmProvider` with `LLM_BACKEND=vertex`,
  project `habeas-codus`, location `global`, authenticated by ADC. Returned schema-valid JSON
  (`{"ok": true, "note": "Operation completed successfully."}`, 83 in / 276 out tokens,
  ~$0.001). Confirms the vertex branch and Vertex structured output both work.

## Not done / next step

- Set the Agent Platform **Spend Cap** and project budget interaction as described above.
- `backend/.env` (local, gitignored) still has an old comment saying there is no Vertex path;
  local works as-is since `LLM_BACKEND` defaults to `developer`.
- When deployed, confirm the Cloud Run service env sets `LLM_BACKEND=vertex` + Gemini model
  ids, then run one real analysis end to end.
