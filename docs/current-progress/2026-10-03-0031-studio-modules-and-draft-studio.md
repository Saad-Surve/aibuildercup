# Project studio layer + versioned draft studio

## What I did

Turned the project page into a **studio router** instead of one combined video wall, and
added a second project kind — a **versioned writing studio**.

1. **Project kinds.** `CreateProject` now takes `kind: "video" | "draft"` plus a
   `draftFormat` (`written` | `script`) and a seed `draftBrief`. The creation dialog is a
   two-card chooser; picking a draft asks for topic, audience, tone, language, platform,
   and notes, then opens the draft studio and generates the first draft.
2. **Video studio = a layer before the combo.** Opening a video project now lands on an
   **Overview** module grid (source video pinned left, modules right). Clicking a module
   opens it at `?module=transcript|review|captions|packaging|localization`. A `ModuleNav`
   tab strip keeps the video and every module one click apart.
3. **Prerequisite gating with shadcn `Marker`.** Transcript, Review + Findings, Burn
   Captions, and Localization need a transcript. When it is missing, the module renders a
   `Marker` step rail — *upload video → generate transcript → then the module unlocks* —
   with the **Generate transcript** action inline. Added the base-ui `marker.tsx`
   component from the shadcn registry.
4. **Burn Captions is its own module.** Removed "Burn captions onto video" from the
   transcript export dropdown. Extracted the caption UI into a reusable `CaptionBurnPanel`
   (the dialog is now a thin wrapper) and mounted it in the Burn Captions module.
5. **Packaging & Localization placeholders.** Thumbnail concepts, infographic clips, and
   title/description/tags; transcript translation and video dubbing. All inert, final
   layout, "Coming soon".
6. **Draft studio.** Left: a document of typed blocks (heading/paragraph/scene), each with
   an immutable `versions[]` history and a version picker. Right: a chat writing partner.
   Assistant replies become new block versions; the first keystroke on an assistant version
   forks a user version. "Three alternatives" adds variants; selecting a phrase shows a
   **Vary "…"** action that rewrites only that phrase as a new version. Export as Markdown,
   plain text, or an all-versions Markdown dump.
7. **Mixed project cards.** Cards branch on `kind`: video keeps the poster/duration/size,
   drafts get a paper preview plus word/block/updated counts from `draftSummary`.

## Changes

### Contract (`contracts/openapi.yaml`)

- `CreateProject` gained `kind`, `draftFormat`, `draftBrief`; `Project` gained `kind`,
  `draftFormat`, `draftSummary`.
- New schemas: `DraftFormat`, `DraftStatus`, `DraftBlockType`, `DraftBrief`, `DraftVersion`,
  `DraftBlock`, `DraftMessage`, `DraftSummary`, `Draft`, `GenerateDraftRequest`,
  `SaveDraftRequest`, `AssistMode`, `AssistDraftRequest`.
- New paths: `GET`/`PUT /projects/{projectId}/draft`, `POST .../draft/generate`,
  `POST .../draft/assist`.

### Backend

- `schemas/draft.py` — the draft model; `schemas/projects.py` — kind/format/summary.
- `services/paths.py` + `firestore_service.py` — `draft_path` (`.../draft/main`).
- `services/draft_service.py` — `get`/`ensure`/`save`/`generate`/`assist`. The LLM only
  proposes text; the service turns each proposal into a new `versions[]` entry. Deterministic
  fallback draft when the model is unavailable.
- `services/project_service.py` — `kind`/`draftFormat`/`draftSummary` on create; new
  `update_draft_summary` keeps the project card in sync.
- `api/draft.py` + `api/projects.py` seeding `draft/main` on draft create; `dependencies.py`
  + `main.py` wire the service/router.

### Frontend

- New `lib/studio.ts` (module metadata), `lib/drafts.ts`, `lib/draft-export.ts`.
- New `components/ui/marker.tsx`; `components/projects/video-studio.tsx` (the former
  workspace logic + module routing); `components/projects/studio/` (`module-grid`,
  `module-nav`, `transcript-gate`, `captions-module`, `packaging-module`,
  `localization-module`); `components/projects/draft/` (`draft-workspace`,
  `draft-document`, `draft-chat`, `draft-brief-dialog`).
- `project-workspace.tsx` is now a thin router (project query + realtime socket) that
  branches on `kind`.
- `caption-burn-dialog.tsx` split into `CaptionBurnPanel` + dialog wrapper;
  `transcript-panel.tsx` lost the burn-captions export item; `create-project-dialog.tsx`
  gained the kind chooser; `project-card.tsx` branches on kind; dashboard/projects copy
  updated.

### Docs

- `db-design.md` (project fields + `draft/main`), `contracts/firestore.md` (tree + draft
  doc), `api-design.md` (Drafts section), `frontend-plan.md` (studio router + draft studio).

## Structural changes

- Firestore: project docs gain `kind`, `draftFormat`, `draftSummary`; new
  `draft/main` document. It lives under the project subtree, so the existing recursive
  project/account delete removes it with **no delete-path changes**.
- API: one new route group; three additive `Project` fields and additive `CreateProject`
  fields, so the web client cannot drift.

## What I decided / discovered

- **Versioning unit = block.** A "word, phrase, or paragraph" version is just a block whose
  text changed: rewrites, alternatives, and phrase-level variation all append an immutable
  version and move `activeVersionId`. That keeps one simple model for all three.
- **Editing an assistant version forks.** The first keystroke on an assistant version
  creates a `My edit` user version rather than overwriting the model's wording, so the
  original stays recoverable. Subsequent keystrokes edit that user version in place.
- **React Query cache is the draft document.** Edits write optimistically to the cache and a
  900 ms debounce persists them; `assist` flushes the pending save first so the model always
  sees the latest text, then replaces the cache from the server response.
- **Gate, don't hide.** The `Marker` rail states the one missing prerequisite and performs
  it inline, which is friendlier than hiding the module.
- **`oxfmt` note:** running `bun run format` rewrites 44 pre-existing files (CRLF working
  tree vs LF), so I formatted only the touched files and reverted the collateral. All new
  and modified files pass `oxfmt --check`; the repo-wide check still flags the pre-existing
  CRLF files on Windows, as before.

## Verification

- Backend: `uv run ruff check .` clean; `uv run mypy app` clean (79 files); app imports and
  exposes the three draft routes + schemas in `app.openapi()`.
- `contracts/openapi.yaml` parses with `yaml.safe_load`; draft paths, `Project`/`CreateProject`
  fields, and draft schemas present.
- Web: `bunx tsc --noEmit` clean; `bun run lint` (oxlint) clean; `bun run lint:eslint`
  0 errors (one pre-existing `<img>` warning); `bun run build` succeeds.

## Not done / next step

- Uncommitted. Say the word and I'll commit + push.
- Packaging, Localization, and the draft "share/duplicate project" are placeholders.
- Draft generation/assist calls Gemini (`model_orchestrator`, flash-lite) synchronously in
  the request. If it ever feels slow, move `generate`/`assist` behind a job + realtime event
  like transcription.
- Possible follow-up: a project-level `kind` filter/tab on the projects page once both kinds
  are common.
