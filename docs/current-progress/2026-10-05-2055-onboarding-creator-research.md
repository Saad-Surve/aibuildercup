# Onboarding: research the creator from public links (grounded)

## What I did

Added an optional first onboarding step where a creator pastes public profile links (YouTube,
Instagram, X, Facebook, TikTok, LinkedIn). One grounded Gemini call (Grounding with Google
Search) researches them and prefills the onboarding answers, so the persona form arrives
populated. The creator reviews/edits each step as before and can skip the import entirely.

Flow: `welcome -> import -> identity -> topics -> audience -> style -> platforms -> persona -> done`.
On the import step the primary button becomes "Research with Gemini" when links are present; it
runs the research and stays on the step so the result + sources are visible, then becomes
"Continue". "Research again" / "Try again" is offered on the step.

## Backend

- `POST /api/onboarding/research` (`api/onboarding.py`), request `{ links: string[] }`, response
  `{ answers, sources, queries, searchSuggestions }`.
- New `services/persona_research.py`: `PersonaResearchService` calls
  `providers.llm.complete_json(..., grounding=True)` with a strict JSON schema. It validates every
  value against the same allow-lists the web form uses, infers `platforms` from link hostnames as
  a reliable signal, merges model-emitted `sources` with the provider grounding chunks, and
  returns the Search Suggestions HTML (Google's terms require rendering it).
- New config: `model_research` (default `gemini-3.1-flash-lite`),
  `onboarding_research_enabled` (default true), `onboarding_research_max_links` (default 6).
- `UserService.save_onboarding_research` merges answers into `onboarding.answers`, stores
  `creatorLinks`, and records grounding provenance under `onboarding.research`. All of it is on
  the user document, so account deletion covers it — no extra delete wiring.
- Wiring: `dependencies.get_persona_research_service`; schemas in `schemas/onboarding.py`.

## Contract & docs

- `contracts/openapi.yaml`: new path + `OnboardingResearchRequest`, `OnboardingResearch`,
  `ResearchSource` schemas; added `BadRequest` / `Forbidden` shared responses.
- `contracts/firestore.md`: onboarding/research shape on the user document.
- `docs/technical-design/api-design.md`, `backend-plan.md`, `frontend-plan.md` updated.

## Frontend

- `lib/onboarding.ts`: new `import` step; `creatorLinks` answer; `parseProfileLinks` and
  `mergeResearchAnswers` helpers (research never clobbers a value the creator already typed).
- `components/onboarding/steps.tsx`: `ImportStep` + `ResearchSummary` (sources, query chips, and
  the Search Suggestions HTML rendered raw, same as `GroundingPanel`).
- `components/onboarding/onboarding-flow.tsx`: `import` state (`research`, `researchTried`,
  `researchError`), `runResearch`, research-first `goNext`, and dynamic button label. The import
  step is onboarding-only; edit mode keeps its existing flow (starts at identity).
- `lib/types.ts`: `OnboardingResearch` / `OnboardingResearchSource`.

## Verification

- `uv run ruff check .` clean; `uv run mypy app` clean (116 files).
- `bun run lint` (oxlint) clean; `bun run build` (Next 16, includes TypeScript) clean.
- One-off check of the pure helpers (`_normalize_links`, `infer_platforms`, `_clean_answers`,
  `_clean_sources`): invalid/space/`ftp` links rejected, enums filtered, sources deduped.
- Live end-to-end pass: researched MKBHD's links and the prefilled answers/sources came back
  correct (confirmed by the product owner).

## Gotchas

- Grounding with Google Search is billed per query after the free tier. It is one call per
  submit and gated by `ONBOARDING_RESEARCH_ENABLED`.
- In JSON mode `groundingChunks` can be empty even when the model searched (same as the truth
  reviewer), so the model-emitted `sources` are the primary citation path; the UI merges both.
- `mergeResearchAnswers` fills only empty fields, so re-running research in edit mode will not
  overwrite the creator's own edits. Deliberate.

## Not done / next step

- Live grounded call verified end-to-end (MKBHD). No follow-up needed unless we broaden platforms.
- Could reuse `creatorLinks`/`research` later (e.g. show provenance on the profile page, or seed
  the YouTube content sync from a linked channel instead of OAuth).
