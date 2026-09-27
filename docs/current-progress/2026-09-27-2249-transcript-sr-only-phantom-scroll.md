# Transcript editor: phantom page scroll from `sr-only` escaping the scroller

## Symptom (from the user's screenshots)

On `/projects/transcript?projectId=…` the window could scroll ~2800px into empty white space
below the editor ("more space below the html tag"). `html` was 632px tall while
`html.scrollHeight` was ~3409px, and the transcript `<ol>` measured 2932px — which made it
look like the list was the cause. It was not.

## Root cause

The transcript scroller was clipping the list correctly
(`clientH 98` vs `scrollH 2992`, `overflow-y: auto`). The leak came from inside the rows:

- Each row's play / insert / delete `<Button>` contains a `<span className="sr-only">`.
- Tailwind's `sr-only` is `position: absolute`.
- The scroller (`CardContent`) had `overflow-y-auto` but **no positioned ancestor**
  (`position: static` all the way up), so the `sr-only` spans resolved their containing block
  to the **initial containing block** (the document).
- An absolutely positioned box whose containing block is the ICB is **not clipped by the
  scroller's overflow**. Each span sat at its static position (one row further down the list),
  so the last one landed at y≈3408 and inflated `document.scrollHeight` to 3409.

Measured live on the real page (bearer token + headless Chrome):

| experiment | `html.scrollHeight` |
|---|---|
| base | **3409** |
| `ol { position: relative }` | **632** |
| scroller `{ position: relative }` | **632** |
| scroller `{ contain: paint }` / `{ will-change: transform }` | **632** |
| scroller `{ overflow: hidden }` | 3391 (no help) |
| `html { scroll-snap-type: none }` | 3409 (not related) |

Note: the previous session's "scroll chaining" note (`2026-09-27-1453`) was treating a symptom
of this same bug — the window was genuinely scrollable because of the phantom 2777px, not just
chaining. `overscroll-y-contain` is harmless and kept.

## Fix (one class)

`web/src/components/projects/transcript-editor.tsx` — the segment `<li>` is now
`relative flex items-start …`. That makes each row the containing block for its `sr-only`
spans, so they are clipped by the scroller and no longer reach the document.

## Verified

Live page, headless Chrome, after the change — `html.scrollHeight === innerHeight` at
1024×600, 1030×632, 1280×800, 1600×900; the `<ol>` (69 segments, 2932px) scrolls inside the
card. `bunx tsc --noEmit` clean, `bun run lint` clean.

## Also done (housekeeping / incident)

- Deleted the temporary probe routes `web/src/app/layout-test/` and
  `web/src/app/layout-test/editor/` (both untracked, both were failing `oxlint`).
- The backend on :8080 was hung (unresponsive, `curl` timing out) and was restarted:
  `uv run uvicorn app.main:app --port 8080` (no `--reload`). The hang was likely triggered by
  my creating/deleting a scratch `backend/mktoken_tmp.py`, which made the reload watcher
  restart on Windows. Left running in the background.

## Gotcha for the future

Any `overflow-y-auto`/`overflow-hidden` pane that contains `sr-only` (or any `position:
absolute` element with no positioned ancestor) will leak into the document scroll height.
Give such a pane (or the item that owns the `sr-only`) `position: relative`. The
`transcript-panel.tsx` scroller was checked and does **not** leak (it has no `sr-only`).

## Not done

- Not committed.
- `lg:h-[calc(100dvh-7.5rem)]` on the editor root is still a magic number; it happens to be
  exact today (header 56 + `main` py-8 64 = 120) but is brittle. Left alone deliberately.
- At very short viewports (e.g. 1024×600) the transcript scroller is only ~66px tall. Cramped,
  not broken; a proper fix belongs with the shell owning its own scroll height.

## Follow-up (same session)

- Transcript panel header actions reordered to **Re-run / Edit / Export** and the button label
  "Run transcript again" renamed to **Re-run** (`transcript-panel.tsx`).
- Everything from this feature was committed locally as `8cbcb7c`
  (backend transcript-version endpoint + contracts + web editor/panel + these notes).
  `oxfmt`, `tsc --noEmit`, `oxlint`, `ruff check`, `mypy app` all clean.
