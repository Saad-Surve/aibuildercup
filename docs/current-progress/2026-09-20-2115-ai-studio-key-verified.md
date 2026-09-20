# Progress — 2026-09-20 21:15 IST

Status: **AI Studio key verified working. Gemini 2.5 models are retired for new keys, so the model
registry now points at the flash alias.**

## 1. Key works

`GEMINI_API_KEY` in `backend/.env` authenticates against the Gemini Developer API. A full
`LlmProvider.complete_json` call (persona-shaped, `response_schema` JSON) returned parsed JSON:
`{"markdown": "..."}`. No Vertex involved.

## 2. The 2.5 models are retired

A call to `gemini-2.5-flash` returned `404 "no longer available to new users… use models/gemini-3.6-flash"`.
Probed the key (`models.list` + a live call per candidate):

| model | result |
|---|---|
| `gemini-2.5-flash` | 404 (retired for new users) |
| `gemini-flash-latest` | OK |
| `gemini-3.6-flash` | OK |
| `gemini-pro-latest` | 429 quota exceeded (no Pro on the free tier) |
| `gemini-3.1-pro-preview` | 429 quota exceeded |

So the free tier is flash-only; Pro is quota-blocked.

## 3. Changes

- `app/config.py`: `model_reviewer` and `model_orchestrator` now default to `gemini-flash-latest`
  (rolling alias, resilient to retirement). Image/video/STT ids left as-is; no providers use them yet.
- `.env.example`: `MODEL_REVIEWER` / `MODEL_ORCHESTRATOR` = `gemini-flash-latest`.
- `backend/.env`: updated those two lines in place (the key itself was never read or printed).

## 4. Verification

`uv run pytest` → **93 passed**. `ruff` and `mypy` clean. Live provider call succeeded.

## 5. Notes / next

- The old persona cassette was keyed on `gemini-2.5-pro`, so it can never match again under the new
  model. It is untracked; delete it or leave it, it is inert. The persona flow will now make a real
  (free) flash call.
- The SDK prints an "automatic function calling" deprecation warning on `generate_content`; benign
  for our schema-constrained calls, but worth watching when the google-genai version moves to the
  Interactions API.
- **Production:** `creator-studio-api` still has no `GEMINI_API_KEY`, so its LLM calls will raise and
  persona falls back to the template. Wiring it needs Secret Manager + a `--set-secrets` line in the
  deploy workflow (the key value lives in `.env`; not read). Pending a go-ahead.
