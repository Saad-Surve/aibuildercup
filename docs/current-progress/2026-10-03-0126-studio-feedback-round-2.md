# Studio feedback round 2: bento, revisions split, draft editor, real draft sync

## What I did

Eight follow-ups on the studio/draft work.

1. **Bento overview.** Dropped the "Your studio / Pick a module…" heading. The module grid is
   now a single bento grid: the transcript is a full-width hero and the rest tile in two
   columns, one `gap-3` for all of them (the transcript no longer floats with its own gap).
2. **Review/findings gap.** The right-pane module wrapper had no vertical spacing, so the
   `ReviewPanel` fragment's two cards (Review + Findings) touched. Added `space-y-6` to the
   snap wrapper.
3. **Only New revision + Delete moved below the card.** Split `video-revisions.tsx` into
   `VideoRevisions` (Revision badge + History dialog, stays in the card header) and
   `NewRevisionButton` (moved below). The status pill sits in the header where New revision
   was; below the card is New revision + Delete.
4. **Delete a video project with no video.** The no-source branch of `VideoStudio` now renders
   the delete dialog too, so a video project still in `draft` can be removed.
5. **Required-field asterisks.** `FieldLabel` gained a `required` prop that appends a red `*`;
   applied to project name, draft topic, and the brief/editor name fields.
6. **Draft document is a snap pane.** `DraftDocument` now uses `WORKSPACE_PANE_SNAP` and its
   body scrolls internally, so it snaps level with the chat and the page does not grow.
7. **Free-flow draft editor.** Removed the `scene` block type entirely (frontend type, block
   icons/labels, add button, backend enum, fallback, export prefix). Only headings and
   paragraphs remain.
8. **Chat ↔ draft sync fixed.** The assist response schema now supports `clearDraft` and
   `removeBlockIds`; the service clears/removes before applying edits, and a deterministic
   `_looks_like_clear` fallback clears when the creator clearly asked for it but the model
   omitted the flag. The prompt now forbids claiming a change that was not returned. The
   workspace always renders the chat (even when the draft is empty), so the confirmation is
   never hidden by the empty state. Added a dedicated `model_writer` (Gemini) config for the
   draft studio instead of reusing the orchestrator id.

## Changes

### Backend

- `schemas/draft.py` — `DraftBlockType` is `heading | paragraph`; `_to_draft` already coerces
  unknown legacy types to paragraph.
- `services/draft_service.py` — `ASSIST_SCHEMA` gains `clearDraft`/`removeBlockIds`;
  `_parse_assist` returns them; `assist` applies clear/remove; `_looks_like_clear` fallback;
  `ASSIST_SYSTEM` tightened; fallback draft no longer emits a scene; uses `model_writer`.
- `config.py` + `.env.example`/`.env.deploy.example` — `model_writer` (Gemini).

### Web

- `components/projects/studio/module-grid.tsx` — bento, no heading.
- `components/projects/video-revisions.tsx` — split into `VideoRevisions` + `NewRevisionButton`.
- `components/projects/video-studio.tsx` — status pill + revisions in the header, New
  revision + Delete below, delete in the no-video branch, `space-y-6` on the module wrapper.
- `components/projects/draft/draft-document.tsx` — snap pane + internal scroll, no scene.
- `components/projects/draft/draft-workspace.tsx` — always two-column (chat never hidden).
- `components/ui/field.tsx` — `FieldLabel required`.
- Forms + `lib/types.ts` + `lib/draft-export.ts` — required markers, no scene.

### Contracts/docs

- `openapi.yaml` — `DraftBlockType` enum drops `scene`.
- `db-design.md` — draft block type example drops `scene`.

## What I decided / discovered

- The clear bug was the schema, not Gemini: the model replied but had no field to express
  "clear", so the service applied nothing while the reply claimed success. Adding
  `clearDraft` (plus the heuristic) makes the reply and the document agree.
- Legacy drafts with `scene` blocks still load: `_block_type`/`_to_draft` coerce unknown types
  to `paragraph`, so no migration is needed.
- The draft chat is part of the layout, not a conditional branch, so clearing the draft leaves
  the conversation visible.

## Verification

- Backend: `ruff` clean, `mypy` clean (79 files).
- Web: `tsc` clean, `oxlint` clean, `eslint` 0 errors (one pre-existing `<img>` warning),
  `next build` succeeds; dev server serves the module routes (200) with no runtime errors.

## Not done / next step

- Uncommitted (the previous studio/draft pass is `cf8e9cb`).
- If the writer still feels weak, point `MODEL_WRITER` at a stronger Gemini in `.env`.
- Assist edits are still matched by exact `blockId`; a hallucinated id is dropped. If that
  shows up, add block indices to the assist context.
