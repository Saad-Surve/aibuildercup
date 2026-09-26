# Progress — 2026-09-25 08:15 UTC — Equal panes, status honesty, HQ posters

Uncommitted (not requested — commit only on ask). No backend changes this round.

## Equal panes, one scroll (replaces sticky + viewport cap)

- Last round's sticky transcript felt detached ("scrolls independently") and
  heights still differed. New approach: `SplitPanes` measures the video
  column with a ResizeObserver and caps the transcript column to that exact
  height (min 360px so short videos stay usable). The transcript card fills
  the capped column and its list scrolls inside; the page itself scrolls as
  one unit. Video never grows, transcript never exceeds it.
- 2-pane is now the default for every state with a video (processing,
  failed, ready) — no more layout switch when the transcript lands.

## Video card bleed + tighter overview

- Video card is square (`rounded-none`) with padding only on the header
  (`px-3 pt-3 pb-2`); the player bleeds edge-to-edge (`px-0 pb-0`), so the
  video itself keeps square corners as originally asked.
- Overview spacing tightened: `space-y-4` container, `gap-4` grid.

## Row baseline fix

- Rows are now dot · (timestamp + text in one `items-baseline` flex) ·
  actions. The timestamp and the first text line share a true baseline
  across the two font sizes, which is what felt "off" before (centered
  blocks with mismatched cap heights). Text stays `tracking-normal`,
  left-aligned, wrapping.

## Non-blocking retranscribe/delete

- Both confirm handlers now close the dialog immediately and run in the
  background with toasts — no more blocking "Working…" modal.

## Processing status honesty (Image 3)

- `ProcessingStatusCard` takes `projectId` and on failure shows the REAL
  reason (job `error.message` first, project note as fallback) instead of
  the generic line; the stale progress bar is hidden on failure and replaced
  with a "Try again" button (retranscribe + query refresh + toast).

## High-quality thumbnails

- Poster capture is now 960px wide at JPEG 0.92 (was 480px / 0.7). Cache key
  bumped to `hc-poster-v2:` with NO fallback to old keys, so every blurry
  thumbnail recaptures at full quality on next view (local blob or the
  bounded fetch); purge clears all key generations.

## Verification

- Web: `oxlint`/`oxfmt` clean, `eslint` 0 errors (1 pre-existing `<img>`
  advisory), `bun run build` passes.
- Backend (untouched): `pytest` 171 passed.

## Gotchas

- Equal panes rely on ResizeObserver + a flex column with `max-h` via a CSS
  var (`xl:max-h-[var(--pane-cap)]`); below xl the panes stack uncapped.
- Short videos (< 360px column) let the transcript define the row height via
  the 360px floor — deliberate usability minimum.

## Next

- Caption `<track>` from transcription; backend-generated `thumbnail` assets;
  per-card delete menus; Audience/Connections/Settings pages (unchanged).
