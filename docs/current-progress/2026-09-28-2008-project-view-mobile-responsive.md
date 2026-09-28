# Make the project view mobile responsive

## What I did

The project workspace (`/projects/view`) overflowed horizontally on phones: the page
had a sideways scrollbar and the workspace header controls ran off the edge. I traced
it with a temporary headless-Chrome probe (rendered the workspace chrome with mock data
in 320/390/430/768/1280px iframes and measured `documentElement.scrollWidth`), fixed the
causes, then deleted the probe.

**Root cause.** The workspace's two-pane wrapper was
`grid gap-6 lg:grid-cols-2`. Below `lg` that is an *implicit* `auto` grid column, whose
minimum size is the widest descendant's min-content. Two descendants have huge min-content:
the injected Google Search Suggestions HTML (arbitrary width, can be >900px) and long
unbroken transcript/suggestion tokens. The auto column grew to 958px and dragged every
card (and the page) with it.

### Fixes

- `project-workspace.tsx` — the pane grid is now `grid-cols-1 gap-6 lg:grid-cols-2`
  (explicit `minmax(0,1fr)` column, so no descendant can widen it). Same for the loading
  skeleton grid, whose placeholders now carry an explicit height instead of relying on the
  pane card height.
- `lib/workspace.ts` — panes are `max-h-[min(72vh,40rem)] lg:h-[min(72vh,40rem)]
  lg:max-h-none`: exact fixed height at `lg` (unchanged), content-height capped on phones
  so the page scrolls as one document instead of four nested scrollers. The card body still
  scrolls once it passes the cap.
- `grounding-panel.tsx` — the injected suggestions block is `overflow-hidden break-words
  [&_*]:max-w-full`; the panel shell is `overflow-hidden`.
- `transcript-panel.tsx` / `findings-panel.tsx` — segment text and finding suggestions are
  `min-w-0 break-words` so long tokens wrap instead of forcing width.
- `page-header.tsx` — the actions row wraps; title/description `min-w-0 break-words`.
- `transcript-panel.tsx` / `review-panel.tsx` — header action groups wrap; the desktop-only
  "Click a segment to jump there" hint is `hidden sm:inline`.
- `heatmap-tracks.tsx` — the track label column is `w-20 sm:w-[8.5rem]` and gaps tighten on
  phones; the five ruler ticks drop to 0/50/100% below `sm` so labels stop colliding.
- `reviewer-footage.tsx` / `caption-burn-dialog.tsx` — responsive grids get explicit
  `grid-cols-1` base tracks.
- `app-shell.tsx` — `main` gets `min-w-0`.
- `ui/dialog.tsx` / `ui/alert-dialog.tsx` — content is `w-[calc(100%-2rem)]` so dialogs keep
  a margin on phones instead of spanning edge to edge.

## Structural changes

UI only. No contract, schema, backend, or data changes.

## What I decided / discovered

- A Tailwind responsive grid (`grid lg:grid-cols-2`, no base `grid-cols-*`) is an implicit
  `auto` column on mobile, so *any* wide descendant spills the whole page. Always set a base
  `grid-cols-1` (or `minmax(0,1fr)`) when intrinsic-width content can appear.
- `truncate` and `break-words` do **not** shrink min-content (`break-word` only breaks on
  overflow); `overflow-hidden` on a wrapper does not stop its child's min-content from
  widening an auto track either. Constraining the track is what actually fixes it.
- The workspace is the first screen where generated, unbounded text (grounding HTML,
  transcript tokens) sits inside an intrinsically-sized layout; other pages use explicit
  column counts or definite-width scrollers.

## Verification

- Headless probe: `docScrollWidth == viewport` at 320, 390, 430, 768, 1280 with a synthetic
  900px grounding block and a long unbroken finding token. Probe deleted.
- `bun run lint` — clean. `bun run lint:eslint` — only the pre-existing `no-img-element`
  warning in `project-card.tsx`. `bun run build` — passes.

## Not done / next step

- Not visually verified on a real device; the probe covered layout width, not touch
  behaviour or the video.js control bar.
- The desktop fixed-pane snap model is unchanged; if the natural-height mobile panes are
  unwanted, revert `WORKSPACE_PANE_HEIGHT`.
- The rest of the responsive/accessibility pass (frontend-plan item 16) is still open —
  dashboard, projects list, transcript editor, profile, dialogs beyond the workspace.
