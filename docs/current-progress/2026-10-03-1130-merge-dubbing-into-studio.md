# Merge incoming studio work with the local dubbing feature

## What I did

The local branch had a complete but untested **dubbing / localization** feature sitting as
uncommitted changes, while `origin/main` had advanced 5 commits (project studio layer, video
revisions, thumbnail studio, draft studio, real caption-render progress). The dubbing work
overlapped many of the same backend files, so I:

1. Stashed the local work (`git stash push -u`), fast-forwarded `main` to `origin/main`
   (`e8e4b28`), then popped the stash.
2. Resolved the 8 conflicted files by keeping the incoming work and re-applying ours on top.
3. Wired the real dubbing panel into the incoming **Localization** studio module (incoming only
   had a static placeholder with disabled buttons).

Incoming is treated as the working baseline; our changes were adapted to it everywhere.

## Changes

### Conflicts resolved (incoming kept, ours re-added)

- `backend/app/dependencies.py` — kept incoming `get_draft_service`, `get_thumbnail_service`,
  `ThumbnailScheduler`; re-added `get_localization_service`, `DubScheduler`.
- `backend/app/main.py` — kept `draft` and `thumbnails` routers; re-added `localizations`.
- `backend/app/services/paths.py` — kept thumbnail paths; re-added `localizations_collection_path`,
  `localization_path`, `localization_object_path`.
- `backend/app/workers/caption_worker.py` — kept incoming `run_ffmpeg_with_progress`; kept our
  `stage_source` extraction (now imported from `app/services/source_media.py`). Import list is
  `VideoToolError, ffmpeg_available, run_ffmpeg_with_progress` (no more local `_stage_source`).
- `contracts/firestore.md` — kept draft + thumbnail sections; re-added the Localizations section.
- `contracts/openapi.yaml` — incoming was deeply interleaved with ours. Rather than untangle the
  markers, I regenerated the file from **incoming** and programmatically re-inserted the four
  localization paths (before the thumbnails path) and the eight `Localization*` schemas (before
  `AnalysisDimension`). Validated with `yaml.safe_load`; all localization + thumbnail paths and
  schemas present.
- `web/src/lib/types.ts` — took incoming and appended the localization types (purely additive).
- `web/src/components/projects/project-workspace.tsx` — took **incoming wholesale**. It is now a
  router that delegates to `VideoStudio` or `DraftWorkspace`; our old-layout `DubbingPanel` insert
  no longer made sense there.

### Frontend integration (ours adapted to incoming structure)

- `web/src/components/projects/studio/localization-module.tsx` — now takes `projectId` and renders
  the real `DubbingPanel` in place of the static "Video dubbing" mock card. The "Transcript
  translation" preview card is untouched. Removed the now-unused `Waveform` mock and its icons.
- `web/src/components/projects/video-studio.tsx` — passes `projectId` to `LocalizationModule`.
- `web/src/lib/studio.ts` — `localization` module flipped `ready: false` → `true` (it is now a
  real, wired module; it still gates on a transcript via `needsTranscript: true`).
- `web/src/components/projects/dubbing-panel.tsx` — fixed `handleLanguageChange` to accept
  `string | null`, matching the incoming base-ui `Select` `onValueChange` signature.
- `backend/pyproject.toml` / `backend/uv.lock` — kept incoming deps; kept our added
  `google-cloud-texttospeech` and `google-cloud-translate`.

### Auto-merged, verified correct

`backend/app/config.py`, `backend/app/providers/__init__.py` (incoming `ImageGenProvider` + our
`TtsProvider`/`TranslateProvider`), `backend/app/services/firestore_service.py`,
`backend/app/services/video_tools.py` (incoming `run_ffmpeg_with_progress` + our `probe_has_audio`).

## Structural changes

- No API path/schema was removed. The contract now carries both the incoming thumbnail/draft
  surface and our localization surface.
- `contracts/openapi.yaml` was rewritten from incoming rather than marker-merged; the result
  parses and contains the union of both sides.
- New backend files (untracked before, now staged): `api/localizations.py`,
  `providers/translate.py`, `providers/tts.py`, `schemas/localizations.py`,
  `services/dubbing.py`, `services/localization_service.py`, `services/source_media.py`,
  `workers/dub_worker.py`.
- New web files: `components/projects/dubbing-panel.tsx`, `lib/dubbing.ts`.

## What I decided / discovered

- Incoming's `LocalizationModule` was explicitly a **placeholder** (`ready: false`, sample data,
  disabled buttons). Our feature is the implementation of that placeholder, so making it `ready`
  and embedding `DubbingPanel` is the natural merge — not a dismissal of incoming.
- `git stash pop` labels: "Updated upstream" = incoming (`origin/main`), "Stashed changes" = our
  local work. That guided every resolution.
- Incoming base-ui `Select.onValueChange` now passes `(value: string | null, details)`; direct
  `(value: string) => ...` handlers no longer type-check. Fixed ours to match.
- The pre-merge local work is recoverable from the dropped stash commit
  `55660dbcc55161ee365e31eb96839a94a2a5627c` (reflog) if needed.

## Verification

- `backend`: `ruff check .` clean; `mypy app` **Success: no issues found in 93 source files**.
- `backend`: `uv lock --check` → resolved 92 packages, clean.
- `backend`: `app.openapi()` builds; localization (4), thumbnail (5), draft (4), caption (4)
  routes all wired.
- `web`: `bun run lint` (oxlint) clean; `bun run lint:eslint` 0 errors (1 pre-existing
  `<img>` warning in incoming `project-card.tsx`); **`bun run build` succeeds** (TypeScript +
  static export, 11/11 pages).
- `git diff --cached --check` clean; no conflict markers remain; no unmerged paths.

## Not done / next step

- **The merged tree is staged but not committed.** Per the repo rule, I did not commit without
  being asked. Say the word and I will commit (+ push).
- The dubbing feature itself is still **untested end-to-end** against live GCP. Next: start the
  backend and run a dub on a `fixtures/media/` video (`POST /api/projects/{id}/localizations`)
  with Cloud Translation + Text-to-Speech enabled, then confirm the Localization module in the
  studio lists the dub and the download works.
- Optional follow-up: the incoming `LocalizationModule` translation-preview card is still a
  static mock; only dubbing is real. Decide whether to drop it, keep it as a preview, or wire a
  translation-only flow.
