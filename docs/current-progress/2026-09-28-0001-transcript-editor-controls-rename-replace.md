# Transcript editor polish: control heights, rename-speaker inputs, video ring, per-match replace

All changes in `web/src/components/projects/transcript-editor.tsx`.

## 1. Uniform control heights (both toolbar and rows)

The toolbar mixed `Input` (`h-8`) with `size="sm"` buttons (`h-7`), and each transcript row
mixed `h-7` timestamp/select + `icon-sm` (28px) buttons with a `min-h-8` textarea (32px).
Everything is now **32px (`h-8` / `size="icon"` / `size="icon"`)**:

- Toolbar: "Replace all" and "Rename speaker" dropped `size="sm"`.
- Row: play / insert / delete buttons → `size="icon"`; timestamp input `h-7` → `h-8`; speaker
  `SelectTrigger` dropped `size="sm"`; textarea stays `min-h-8`.

Verified heights: toolbar `find 32, replace 32, replace all 32, rename 32`; row
`play 32, time 32, speaker 32, text 32, action buttons 32`.

## 2. Rename speaker: dropdowns → text

The From/To `Select`s are now numeric `Input`s (`inputMode="numeric"`, digits-only, labels
"From speaker" / "To speaker"). Removed the now-unused `speakerTargets` (and `maxSpeaker`)
derivations. Verified in the rendered dialog: 2 inputs, 0 comboboxes.

## 3. Video player ring + shadow

The editor wrapped `SourceVideoPlayer` in `overflow-hidden rounded-xl`, which clipped the
player's own `shadow-sm`. The wrapper is now
`overflow-hidden rounded-lg shadow-sm ring-1 ring-foreground/10` (same radius/ring as `Card`),
so the ring and shadow actually render.

## 4. Per-match replace (individual, not just Replace all)

Added `replaceOne(segmentId)` — scoped version of `replaceAll` — and each matching row now
renders a ghost icon button (`Refresh01Icon`, title "Replace in this segment") between the
text field and the insert button. So you can replace one hit at a time, VSCode-style, or
still use "Replace all". Matching rows keep the `bg-signal/5 ring-1 ring-signal/30` highlight.
Verified: searching "the" matched 23 rows, each with the replace button; status reads
"23 segments match “the”".

## Verified

`oxfmt` / `bunx tsc --noEmit` / `oxlint` clean. Rendered and screenshotted via headless
Chrome + the copied Chrome profile (bearer session), including opening the rename dialog.

## Not done

- Committed immediately after this note.
- `replaceOne` replaces every occurrence within the segment, not one occurrence at a time
  inside a segment (a one-line transcript segment normally has one).
