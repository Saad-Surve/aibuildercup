# Progress — 2026-09-26 05:56 UTC — switched reviewer/orchestrator LLM to Gemma 4

Goal: stop hitting Gemini free-tier rate limits during analysis. Tested whether Gemma
could replace Gemini as the reviewer model, then switched the default model registry.

## Finding that changed the plan (important)

I expected Gemma to be blocked: Google's structured-outputs docs list **only** Gemini
models, and Gemma 3 returned `400 "Json mode is not enabled for models/gemma-3-27b-it"`.
That is outdated for Gemma 4. A live probe against `gemma-4-26b-a4b-it` through
`LlmProvider`'s exact config (`response_mime_type="application/json"` +
`response_schema=FINDINGS_SCHEMA`) returned **valid schema-conforming JSON** (5/5
findings survived `normalize_findings`; JSON-mode-only also worked, 6/6). So the
provider needed **no code change** — the swap is config-only.

Probe harness: `/var/folders/k5/kg4gky595wg3ccc5xzw09r380000gn/T/opencode/gemma_probe.py`
(throwaway, outside the repo). Runs the real `TruthEvidenceReviewer` prompt + schema,
tests A=controlled-generation, B=JSON mode, C=prompt-only, and hard-times-out per call.

## What changed

- `backend/app/config.py`:
  - `model_reviewer` / `model_orchestrator`: `gemini-flash-latest` -> `gemma-4-26b-a4b-it`.
  - `llm_input_price_per_mtok` / `llm_output_price_per_mtok`: `0.75/3.75` -> `0.0/0.0`
    (Gemma is free). Cost estimates for Gemma runs are now 0, so
    `max_project_cost_usd` will never trip on Gemma.
- `backend/.env.example`: same `MODEL_REVIEWER` / `MODEL_ORCHESTRATOR` default swap.

No change to `providers/llm.py`, agents, schemas, or contracts.

## Why Gemma 4

- Free, and far more generous free-tier quota than Gemini flash (Gemma 3 was
  ~30 RPM / 15K TPM / 14,400 RPD), which targets the actual 429 problem.
- Supports system instructions, thinking toggle, image input, function calling, and
  (empirically) controlled generation via the Gemini Developer API.
- Reversible: set the two `MODEL_*` vars back to `gemini-flash-latest` (and restore the
  prices) for Gemini flash-class quality.

## Gotchas / risks

- **Latency is variable.** Probe runs returned in 16 s and 21 s, but a later controlled
  generation run exceeded a 75 s per-call timeout. Analysis fires 13 reviewers at
  `max_reviewer_concurrency=4`, so wall-clock per run is likely longer than with Flash.
  Watch the job timeout if analysis starts failing on time, not quota.
- **Quality is unproven.** The flagship heatmap's nuance may drop vs Flash. This was one
  truth-reviewer sample, not the full 13-dimension panel. Worth an A/B on a real
  `fixtures/media/` video before demoing.
- `gemma-4-26b-a4b-it` is not in Google's structured-output support table; it works
  today but is not a documented guarantee. The prompt already says "JSON only", and
  `normalize_findings` tolerates minor shape drift, so a future regression degrades
  rather than crashes.
- `Gemma 4` models available on the API: `gemma-4-26b-a4b-it`, `gemma-4-31b-it`.
- **31B is higher quality but currently unavailable.** Per Google's model card, the dense
  31B beats 26B-A4B on most benchmarks (MMLU-Pro 85.2 vs 82.6, GPQA 84.3 vs 82.3,
  LiveCodeBench 80.0 vs 77.1, HLE 19.5 vs 8.7) and is far better at long-context
  retrieval (MRCR v2 128k 66.4 vs 44.1), which matters for long transcript windows.
  26B-A4B is MoE (~3.8B active of 25.2B total) so it is much faster and was reliably
  available. Two live `gemma-4-31b-it` probes both returned `503 UNAVAILABLE — high
  demand`, so the default stays on 26B-A4B for availability.

## Verified

- Backend: `pytest` **272 passed**, `ruff` clean, `mypy` clean.
- Live probe: Test A and Test B both parse and normalize against the real schema.

## Next step

Run a real end-to-end analysis on a `fixtures/media/` video with Gemma default and
compare the heatmap against a Gemini run. If quality holds, done; if not, keep Gemma for
the cheap dimensions and route the flagship dimensions back to Gemini, or try
`gemma-4-31b-it` once its availability on the API recovers (higher quality, slower,
was 503 during this session).
