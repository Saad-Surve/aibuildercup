# Persist speaker names: `speakerLabels` on `TranscriptUpdate`

## What I did

Closed the gap flagged in the previous note: saving an edit could carry speaker labels but had no
way to *change* them, because `TranscriptUpdate` had no `speakerLabels` field. Added the field
end-to-end so the editor's "Rename speaker" dialog can name a speaker and have it survive the save.

## Structural changes (contract → backend → web)

- **`contracts/openapi.yaml`** — `TranscriptUpdate.speakerLabels`: `[object, "null"]`,
  `additionalProperties: string`. Documented as "speaker index to display name; omitted or null
  keeps the active transcript's labels".
- **`backend/app/schemas/transcripts.py`** — `TranscriptUpdate.speakerLabels: dict[str, str] | None = None`.
- **`backend/app/api/transcripts.py`** — `update_transcript` forwards `speaker_labels=payload.speakerLabels`.
- **`backend/app/services/transcript_service.py`** — `update()` gained
  `speaker_labels: dict[str, str] | None = None`. Semantics: **an explicit map wins; when omitted
  the active transcript's labels are carried forward**. Passed through to `_persist_segments()`.
- **`web/src/lib/projects.ts`** — `updateTranscript` input type gained
  `speakerLabels?: Record<string, string> | null`.
- **`web/src/components/projects/transcript-editor.tsx`** — a `labelsDraft` state sits alongside
  `draft`, so labels are edited locally and only committed on Save (same model as segments):
  - `dirty` is now `draft !== null || labelsDraft !== null`; Discard clears both.
  - Save sends `speakerLabels` (the full current map).
  - The "Rename speaker" dialog gained an optional **Name** field. Applying it:
    - moves the merge label `from` → `to` when merging (falling back to the target's existing
      name), then applies the typed name — so a merged speaker does not lose its name;
    - sets the name directly when `from === to`.
  - The per-segment speaker `Select` now shows the label (`Host`) instead of `S1` when one
    exists, so the rename is visible without leaving the editor.

## Decisions / gotchas

- **Explicit map wins, omission preserves.** The backend cannot distinguish "clear all names"
  from "field may be an old client"; a provided map is treated as authoritative and `None`/absent
  falls back to the active transcript. The web editor always sends the full derived map, so this
  is equivalent to replace for the real client, while staying backward compatible.
- Keeping labels in a separate `labelsDraft` (not folded into `draft`) avoids rewriting the
  segment-array editing paths and keeps "dirty" honest for label-only changes.
- `duration_ms` is still carried from the active transcript on edit (see previous note) so a
  rename cannot shrink the timeline.

## Verification (all run, all green)

- `backend/`: `ruff check .` → All checks passed; `mypy app` → Success, 70 files.
- `backend/`: `from app.main import app` → 13 routes; `TranscriptUpdate.model_fields` →
  `['language', 'segments', 'speakerLabels']`; `{'0':'Host'}` parses, absent → `None`.
- `contracts/openapi.yaml` parses as YAML; `TranscriptUpdate.speakerLabels` present with
  `additionalProperties: string`.
- `web/`: `bunx tsc --noEmit` clean; `bun run lint` (oxlint) clean; `bun run lint:eslint` →
  0 errors (1 unrelated pre-existing `<img>` warning in `project-card.tsx`);
  `bun run build` compiled successfully (11 routes incl. `/projects/transcript`);
  the two touched files pass `oxfmt --check`.
- `bun run format:check` reports ~40 **pre-existing** unformatted files (`src/lib/types.ts`,
  `src/lib/realtime.ts`, …) that are untouched here — left alone deliberately to avoid noise.

## Not done / next step

- Still no live GCP run: the full editor path (rename + merge → Save → new version) is only
  statically verified. Worth one e2e pass with a `fixtures/media/` upload, checking that the new
  version keeps its names in both the editor and the read-only transcript card.
- `speakerLabels` keys are stringified indices. A merge renumbers segments but *not* the labels of
  speakers that were not involved, which is correct today because segments keep their indices on a
  plain edit; if segment re-indexing ever remaps speaker numbers, labels must be remapped too.
