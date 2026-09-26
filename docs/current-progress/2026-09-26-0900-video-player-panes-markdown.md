# Progress — 2026-09-26 09:00 UTC — stable player, pinned pane stack, markdown, polish

## Video.js "video disappears"
Root cause: `StudioPlayer`'s init effect had `poster` in its dependency array, and React
rendered the `<video>` node. When the captured frame poster arrived a moment after mount, the
effect tore the player down and rebuilt it on the same node React owned — which is what made the
video vanish. Fix in `source-video-player.tsx`:
- The `<video>` element is now created imperatively and owned by video.js inside a React-owned
  container (`containerRef`), so React never removes a node video.js disposed.
- Init effect deps are `[src, mimeType]` only. The initial poster is read from a ref; later
  poster changes are applied to the live player (`player.poster(...)`).
- Player reports `loadedmetadata`/`durationchange` back through `onDuration`.

## Pinned pane stack (left video + right transcript/review/findings)
- `lib/workspace.ts` now exposes `WORKSPACE_PANE_STICKY` (`lg:sticky lg:top-20`, same offset as
  the video card) and `WORKSPACE_PANE_STACK_SPACER` (`h-[28vh]`).
- Transcript, Review and Findings cards are sticky at the video's top; later cards slide over
  earlier ones in DOM order, so transcript pins first, then Review, then Findings.
- A trailing spacer gives the last pane room to be pulled all the way up (the panes are the same
  height as the video, so without it the last one could never reach the top).

## Video card metadata
- Dropped the `gs://` storage path. Now shows **Duration · Size · Uploaded** (duration from the
  player metadata, falling back to the asset's recorded duration).

## Findings density
- Each row now shows meta + suggestion only. The transcript quote and explanation moved into a
  "Show evidence" `<details>` disclosure (hidden, not deleted).

## State pills
- `ProcessingStatusCard` pill now maps state → colour: **ready/done green**, queued grey,
  in-progress signal, failed destructive. Height is `h-7`, matching `size="sm"` buttons.

## Persona markdown
- `PersonaText` was stripping `**` and only handled `* ` bullets. It now renders headings,
  ordered + unordered lists (the generator emits `*   **Label:** value`), and inline
  **bold** / *italic* / `code`.

## Avatar size
- Header avatar 32 → 38 (button h-11), profile preview 64 → 96, customizer preview 96 → 128.

## Verified
- Web: `bunx tsc --noEmit` clean, `bun run lint` (oxlint) clean, `bun run build` passes.
- Seek-on-click already routes through `creator-studio:seek` from transcript, heatmap bins and
  findings; it was failing because the player was being recreated — now stable.
