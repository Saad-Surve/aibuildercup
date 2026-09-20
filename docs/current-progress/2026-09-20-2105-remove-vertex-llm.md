# Progress — 2026-09-20 21:05 IST

Status: **Vertex AI is gone from the LLM path. The only backend is the Gemini Developer API
(AI Studio), selected by `GEMINI_API_KEY`.**

## 1. What changed

- `app/providers/llm.py`: `_real` no longer constructs a Vertex client. It now raises a clear
  `RuntimeError` if `GEMINI_API_KEY` is unset, otherwise builds `genai.Client(api_key=...)` and logs
  `LLM call via Gemini Developer API (<model>)`.
- `app/config.py`: `gemini_api_key` comment updated to say there is no Vertex path.
- `.env.example`: `GEMINI_API_KEY` is now documented as required for real calls.
- `pyproject.toml` / `uv.lock`: removed the direct `google-cloud-aiplatform` dependency (it only
  existed for Vertex; nothing in `app/` imported `aiplatform` or `vertexai`). This also dropped
  `google-cloud-resource-manager` and `docstring-parser`.
- `tests/test_providers.py`: replaced the "uses Vertex" test with
  `test_llm_requires_api_key`, which asserts the `GEMINI_API_KEY` error and that no client is built.
  The API-key test still asserts `genai.Client` is called with `{"api_key": "test-key"}`.

## 2. Behaviour without a key

- `MOCK_MODE=off`/`auto` + no key + cassette miss → `LlmProvider` raises. `PersonaService` catches
  it, logs, and falls back to the deterministic `build_persona_markdown` template, so onboarding
  still completes offline. Future reviewer/chat callers must decide their own fallback.
- `MOCK_MODE=on` + cassette hit → replays; miss → `CassetteMiss` (also caught by the persona
  service → template).

## 3. Deployment note (action needed)

The `creator-studio-api` Cloud Run service is still deployed with no `GEMINI_API_KEY`; with Vertex
removed, real LLM calls in production now fall back to the template. Production needs the key too.
Recommended: store it in Secret Manager and add `--set-secrets GEMINI_API_KEY=...` to the deploy
step (or a GitHub Actions secret). Not wired yet — waiting on the key.

Local: add `GEMINI_API_KEY=<key>` to `backend/.env` (gitignored). The free tier is fine for dev;
`MODEL_ORCHESTRATOR=gemini-2.5-flash` has a larger free allowance if `gemini-2.5-pro` throttles.

## 4. Verification

`uv run pytest` → **93 passed**. `uv run ruff check .` clean. `uv run mypy app` clean.

## 5. Optional cleanup (not done)

- `infra-plan.md` / `infra/RESOURCES.md` still describe a Vertex AI User role on the API and analysis
  SAs. Harmless to leave, but can be trimmed since the LLM no longer uses Vertex. STT, Translation,
  and TTS are separate APIs and are unaffected.
