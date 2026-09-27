# Transcript editor: header subtitle -> project name, page snap on the video row

## What changed (`web/`)

`web/src/components/projects/transcript-editor.tsx`

- Removed the `PageHeader` description ("… saving creates a new version …"). The title is now
  `Edit transcript │ <project name>` with the same divider treatment the transcript card
  header uses (`<span className="h-4 w-px bg-border" />`).
- Replaced the fixed full-viewport root (`lg:h-[calc(100dvh-7.5rem)]`) with a two-stop page:

  1. **Header stop** — back link + title, `lg:snap-start lg:snap-always lg:scroll-mt-20`.
     Keeping the back link inside the stop is why page snapping can always rest on it.
  2. **Video row stop** — the video + controls row, `lg:scroll-mt-20`.

  The transcript card is **not** a snap stop.

- The video row lives in a section of `lg:h-[calc(100dvh-6.5rem)]` (`6.5rem` = 56px shell
  header + 24px gap above + 24px gap below). Inside: video row (`shrink-0`) + transcript
  (`flex-1`). So once the row snaps at y=80, the transcript fills everything down to y=608
  with an even 24px gap above and below — verified at 1024×600, 1030×632, 1280×800, 1600×900.

`web/src/components/common/page-header.tsx`

- `title` widened from `string` to `ReactNode` so the editor can pass the title + divider +
  project name. All existing string callers are unaffected.

`web/src/app/(app)/projects/transcript/page.tsx` + editor

- New exported `TranscriptEditorSkeleton`, shaped like the real page (back-link line, title
  line, video row, transcript pane). Used both by the editor's query-loading state and the
  route's `Suspense` fallback, so there is no layout jump while loading.

## Gotcha discovered

Tailwind v4 + Turbopack served a **stale stylesheet**: the removed `lg:h-[calc(100dvh-7.5rem)]`
rule was still in the CSS while the new `lg:h-[calc(100dvh-6.5rem)]` was missing, so the
section collapsed to content height (3400px page). Touching `globals.css` did not rebuild it;
restarting `next dev` did. If a newly added arbitrary utility "does nothing", check
`document.styleSheets` for the rule before assuming the class is wrong.

Also: the dev server on :3000 was restarted to clear that cache (`bun dev`, background).

## Verified

`oxfmt`, `bunx tsc --noEmit`, `oxlint` clean. Live page (headless Chrome + bearer token):
the page has exactly two snap stops, snapped geometry is `top gap 24 / bottom gap 24`, and
`html.scrollHeight` is 744 at a 632 viewport (no phantom scroll).

## Not done

- Not committed yet at time of writing (committed immediately after this note).
- The `scroll-mt-20`/`100dvh-6.5rem` pair encodes the shell header height (56px) and the gap
  (24px) in three places; if the shell header height changes, these need to change together.
