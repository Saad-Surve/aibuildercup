# Localization: corpus + glossary + Gemini adaptation + localized captions

## What I did

Continued the dubbing module. The basic pipeline (Cloud Translation → Text-to-Speech →
duration-normalized mux) was already in place from the merge. The missing pieces were the
design's actual differentiator: the **terminology corpus + project glossary**, the **Gemini
cultural-adaptation pass**, and **version tracking**, plus the localized subtitle output.
This closes the "glossary + corpus + TTS + duration-normalized mux" workstream C phase-3 item
(TTS + mux were already done; glossary + corpus + adaptation are now done).

Added a curated corpus, a project glossary the creator edits, a second Gemini pass that fixes
what machine translation gets wrong, SRT output, and the versions every dub was built with.

## Status before this change

Implemented and verified:

- `POST/GET/DELETE /projects/{id}/localizations`, `GET /localization-voices`,
  `GET .../download-url`.
- `dub` job: translate when the source language differs → one TTS take per segment → tempo-bend
  each take into its window → assemble one timeline → mux onto the video (optionally keeping
  the original audio quiet underneath) → upload MP4 + MP3 → mark ready.
- Voice catalog (en, hi, es, fr, de, pt, ja, ar) with per-speaker voice assignment.
- Web: `DubbingPanel` in the Localization studio module (language/voice picker, progress,
  download, delete).

Missing (now added): global corpus, project glossary, Gemini adaptation, corpus/glossary
versions, localized captions.

## Changes

### New backend modules

- `backend/app/assets/corpus/global.json` — the curated MVP corpus: glossary term pairs for
  `en-hi` (rich), `en-es`, `en-fr`, plus a universal trap list (brands, code-mixing) and an
  `en-hi` trap list (idioms, false friends, units/currency, dates, honorifics), versioned.
  Bundled inside the backend image because the Docker build context is `backend/` (Cloud Run
  does not get the `corpus/` folder or the corpus bucket).
- `backend/app/services/localization_corpus.py` — typed loader (`Corpus`, `GlossaryTerm`,
  `Trap`), `corpus_for(source, target)` (merges pair-specific + universal traps),
  `available_pairs()`, `corpus_version()`. Pure data, no SDKs.
- `backend/app/services/localization_adapt.py` — the Gemini cultural-adaptation pass.
  `adapt_translations(sources, drafts, ...)` batches lines, sends source+draft+glossary+traps,
  returns adapted lines in order. **Best-effort**: a failed or wrong-length batch keeps the raw
  machine translation, so a dub never fails on the second pass.
- `backend/app/services/glossary_service.py` — project glossary persistence at
  `users/{uid}/projects/{projectId}/glossary/main`, versioned, with optimistic concurrency and
  an `applicable(...)` reader the worker uses.
- `backend/app/api/glossaries.py` — `GET /glossaries`, `GET/PUT /projects/{id}/glossary`.

### Backend edits

- `config.py` — `model_localization` (used by the adaptation pass).
- `paths.py` / `firestore_service.py` — `glossary_path`.
- `schemas/localizations.py` — `GlossaryTerm`, `Glossary`, `GlossaryUpdate`,
  `CorpusLanguagePair`, `GlobalCorpus`; `Localization` gained `captionsStoragePath`,
  `captionsUrl`, `corpusVersion`, `glossaryVersion`.
- `services/localization_service.py` — snapshots the applicable glossary terms + corpus/glossary
  versions onto the localization at create time (so a later glossary edit cannot change a
  running or finished dub); mints the captions URL; deletes the captions object; `mark_ready`
  takes the captions path; added `captions_path`.
- `workers/dub_worker.py` — runs the adaptation pass after machine translation; builds a
  localized SRT from the translated segments and uploads it as `.../renders/dubs/{id}.srt`;
  `_corpus`, `_build_srt`, `_srt_timestamp` helpers.
- `dependencies.py` — `get_glossary_service`; localization service gets a glossary service.
- `main.py` — registers the glossary router.
- `.env.example` / `.env.deploy.example` — `MODEL_LOCALIZATION`.

### Contracts

- `contracts/openapi.yaml` — `/api/glossaries`, `/api/projects/{projectId}/glossary`
  (GET/PUT), the five new schemas, and the new `Localization` fields.
- `contracts/firestore.md` — the project glossary document and the new localization fields
  (`captionsStoragePath`, `corpusVersion`, `glossaryVersion`, internal `glossaryTerms` snapshot).

### Web

- `web/src/lib/dubbing.ts` — `getGlobalCorpus`, `getGlossary`, `putGlossary`.
- `web/src/lib/types.ts` — glossary/corpus types and the new localization fields.
- `web/src/components/projects/studio/glossary-editor.tsx` (new) — a free-text glossary editor
  (`source = target` per line), showing the corpus version + covered pairs and the glossary
  version, with optimistic-concurrency save.
- `web/src/components/projects/dubbing-panel.tsx` — captions (SRT) download, corpus/glossary
  version line, and the language picker now defaults to the project's first `targetLanguages`
  entry (base-code matched, so `hi-IN` finds `hi`).
- `web/src/components/projects/studio/localization-module.tsx` — renders the glossary editor
  above the dubbing panel; passes `targetLanguages`.
- `web/src/lib/studio.ts` — already marked the localization module ready (previous change).

### Docs

- `corpus/README.md` — notes the runtime bundle location and that GCS/BigQuery ingestion remains
  a follow-up.
- `docs/technical-design/frontend-plan.md` — Localization is no longer described as a placeholder.

## Structural changes

- Two new API paths (`/api/glossaries`, `/api/projects/{projectId}/glossary`), five new schemas,
  five new `Localization` response fields.
- New Firestore document `users/{uid}/projects/{projectId}/glossary/main` (under the project
  subtree, so the recursive delete covers it).
- A localization now snapshots `glossaryTerms` plus `corpusVersion`/`glossaryVersion`; the
  SRT is a fourth artifact under `.../renders/dubs/`.
- The global corpus is a bundled JSON asset; the design's GCS/BigQuery corpus remains the
  ingestion target (loader is the one place to change).

## What I decided / discovered

- The Docker build context is `backend` (`.github/workflows/deploy.yml`), so the corpus must
  ship inside `backend/app/`, not `corpus/`. `corpus/README.md` records this.
- Snapshotting the glossary terms on the localization is how "a localization never mixes
  versions" (design §7) is enforced without keeping every glossary revision around.
- The adaptation pass validates the returned line count and falls back per batch; verified with
  a fake provider (ok / wrong-count / exception / order).
- Incoming base-ui `Select.onValueChange` passes `string | null`; the language default now uses
  base-code matching so a region code from the project still selects the right catalog entry.

## Verification

- `backend`: `ruff check .` clean; `mypy app` **Success: no issues found in 97 source files**;
  `uv lock --check` clean.
- `backend`: `app.openapi()` builds; localization (4) + glossary (2) routes wired.
- Corpus/adaptation smoke test (inline, no test files added): corpus `en-hi` = 8 terms + 8
  traps; adaptation maps correctly, preserves order, keeps drafts on wrong count, keeps drafts
  on exception.
- `web`: `bun run lint` (oxlint) clean; `bun run lint:eslint` 0 errors (1 pre-existing `<img>`
  warning in `project-card.tsx`); `bun run build` succeeds.

## Addendum: remote commit `69fe491`

While this work was staged, `origin/main` advanced one commit
(`69fe491 feat(thumbnails): applied thumbnail becomes the project cover; polish UI`). It adds
`posterStoragePath`/`posterUrl` to the `Project` schema, `coverUrl` on the player, and touches
`project-card`/`sonner`/`thumbnail-panel`. I stashed, fast-forwarded to `69fe491`, and popped —
the changes are in disjoint regions, so the pop was clean (no conflicts). Re-ran all checks on
the integrated tree: ruff, mypy (97 files), `app.openapi()`, oxlint and `bun run build` all
pass. `main` is now level with `origin/main` (`69fe491`) with the localization work staged on top.

## Not done / next step

- The merged tree is **staged but not committed** (rule: do not commit unless asked).
- **Still untested against live GCP.** Next: enable Cloud Translation + Text-to-Speech, then run
  a dub on a `fixtures/media/` video and confirm the adaptation pass improves `en-hi` output and
  the SRT downloads.
- **Localization comparison + flag UI** (design §7/§12) is the main remaining piece: store the
  per-segment source/localized pairs on the localization, add
  `POST /projects/{id}/localizations/{localizationId}/flag`, and a comparison view. This is the
  design's "flag a wrong phrase → candidate corpus entry" loop and was left out to keep this
  change reviewable.
- The `LocalizationModule` "Transcript translation" card is still a static sample; the real
  translation output now lives in the dubbed SRT. Decide whether to drop it or wire it to the
  localized segments.
- Cloud Translation Advanced **glossary registration** (design §6) was not done; the glossary is
  currently enforced in the Gemini pass. Moving it earlier would also constrain the raw draft.
