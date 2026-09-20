# Progress — 2026-09-20 21:45 IST

Status: **Production LLM calls were succeeding and then being thrown away because the cassette
writer failed. Recording is now `auto`-only and non-fatal.**

## 1. The real production failure

After the retry fix deployed, the persona still came back as the template. Cloud Run logs at
`16:06:14Z`:

```
Persona generation failed; using deterministic template
File "/app/app/providers/llm.py", line 57, in complete_json
PermissionError: [Errno 13] Permission denied: '../fixtures'
FileNotFoundError: [Errno 2] No such file or directory: '../fixtures/cassettes/llm'
```

No 503 this time. `LlmProvider._real` returned a good response, then `complete_json` called
`cassettes.save(...)`, which tried to create `../fixtures/cassettes` in the container (CWD `/app`,
so `..` is `/`) and raised. That exception propagated out of `complete_json`, so `PersonaService`
caught it and returned the template — discarding a perfectly good generation.

## 2. Fix

- `app/providers/llm.py`: record a cassette only when `mock_mode == "auto"`. `off` (production) is
  always-real with no cassette side effects; `on` never reaches `_real`.
- `app/providers/cassette.py`: `save` is now best-effort — an `OSError` logs a warning instead of
  raising, so a read-only or absent cassette directory can never discard a real response.
- `tests/test_providers.py`: added `test_llm_off_does_not_write_cassette` and
  `test_cassette_save_failure_is_non_fatal`.

## 3. Why the earlier template outputs happened (two separate bugs)

1. `15:57Z` — a genuine `503 UNAVAILABLE` from `gemini-flash-latest`; fixed by the retry added in
   `817b87d`.
2. `16:06Z` — cassette write failure discarding a successful call; fixed here.

## 4. Verification

`uv run pytest` → **97 passed** (was 95). `ruff` and `mypy` clean.

## 5. Next

Deploy, then regenerate the persona (Profile → Edit persona → Platforms → Generate persona). A
successful generation proves the whole path end to end. If it still shows the template, check the
logs for a fresh error rather than assuming.
