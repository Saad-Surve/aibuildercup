# Draft studio: stronger writer model (3.8-flash), alternatives stay flash-lite

## What I did

The draft studio's main generation and the writing-partner chat were running on
`gemini-3.1-flash-lite` — fast but shallow. Split the model so only the cheap, short-span work
stays on flash-lite.

- `config.py`: `model_writer` default is now `gemini-3.8-flash` (full draft generation + `assist`
  chat). New `model_suggest` default `gemini-3.1-flash-lite` for the `suggest` endpoint
  (alternatives / selection rewrites).
- `draft_service.py`: `suggest()` now calls `model_suggest`; `generate()` and `assist()` keep
  `model_writer`.
- `deploy.yml`: now passes `MODEL_WRITER` and `MODEL_SUGGEST`. **Previously it passed neither**, so
  the deployed writer silently fell back to the config default — which is why the deployed writer
  was flash-lite while the reviewers were already on `gemini-3.8-flash`.
- `.env.example` / `.env.deploy.example` / local `backend/.env` updated.

## Verification

- `uv run ruff check .` clean; `uv run mypy app` clean (111 files).
- Local settings: `model_writer=gemini-3.8-flash`, `model_suggest=gemini-3.1-flash-lite`.
- Deploy run `37180240351` success → revision `creator-studio-api-00083-ltx` with
  `MODEL_WRITER=gemini-3.8-flash`, `MODEL_SUGGEST=gemini-3.1-flash-lite`,
  `MODEL_REVIEWER=gemini-3.8-flash`.

## How the draft LLM works (for the record)

Three calls, all `DraftService -> LlmProvider.complete_json` (`providers/llm.py`): one non-streamed
`generate_content` with `system_instruction`, `response_mime_type=application/json`, and
`response_schema`. Runs off the event loop; retries 429/5xx up to `llm_max_attempts`.

- `generate` (`POST /draft/generate`): brief -> `{title, blocks[]}`.
- `assist` (`POST /draft/assist`, the chat): brief + blocks -> `{reply, title, clearDraft,
  removeBlockIds, blocks[]}`.
- `suggest` (`POST /draft/suggest`): selection + surrounding -> `{suggestions[]}`.

## Remaining levers (not done)

- **Context**: `_generate_blocks` passes only the brief. It ignores the project's transcript,
  persona, and the reviewers' findings — the biggest quality win available.
- **Generation params**: `_generate` sets no `temperature`, `max_output_tokens`, or
  `thinking_config`.
- **Prompt**: `GENERATE_SYSTEM` doesn't use `brief.targetWords` or ask for section count / CTA.
- Silent fallback `_fallback_blocks` (2–4 block template) still masks any model failure.

## Not done / next step

- Re-test the chat/generation on the deployed app; decide whether to feed transcript/persona/findings
  into `_generate_blocks` next.
