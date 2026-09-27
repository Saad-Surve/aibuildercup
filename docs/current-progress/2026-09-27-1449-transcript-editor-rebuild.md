# Transcript editor rebuilt (UI revert + careful rebuild)

## Context

After the shell/scroll incidents, all `web/` changes were reverted to `HEAD`
(`git checkout -- web/` + editor page/component deleted), keeping only backend + contracts.
`image.png` was also removed from tracking (`git rm --cached image.png`, now in
`.gitignore`). The sketch layout from it: video top-left, toolbar top-right, full-width
transcript list below.

This note rebuilds the editor page in the **containment-safe** form.

## What I did

Only `web/` files, normal page flow everywhere, **zero** changes to `app-shell.tsx` or
`globals.css`:

- `web/src/lib/projects.ts` — re-added `updateTranscript(projectId, { language, segments })`
  (`PUT …/transcript`, returns the new active `Transcript`).
- `web/src/components/projects/transcript-panel.tsx` — added an **Edit** button (pencil) that
  routes to `/projects/transcript?projectId=…`, placed between Run and Export.
- `web/src/app/(app)/projects/transcript/page.tsx` — static-export-safe route (query param +
  `Suspense`), mirrors `projects/view`.
- `web/src/components/projects/transcript-editor.tsx` (new) — the editor:
  - Top: bare video player (no card chrome) left; tools card right — Find (+ match count),
    Replace with + **Replace all**, **Rename speaker** (from/to dialog), status text,
    **Discard** / **Save**.
  - Bottom: transcript card, single-line header with divider
    (`Transcript │ N segments · <lang>`), `max-h-[min(70vh,36rem)]` + internal scroll.
  - Each row: seek (play) button, editable `mm:ss` timestamp field with validation (parse,
    past-video-duration reject with toast, Escape/Enter handling), per-row speaker select
    (when diarized), auto-growing text area, per-row **insert-below (+)** and **delete**.
  - **Add segment** button centered at the bottom of the list.
  - All editing is a local draft; Save creates a new backend version (guard: refuses when
    every row is empty); Discard drops the draft. New insert start/end times are clamped to
    the video duration (`videoDurationMs ?? transcript.durationMs`).

## Verified

- `bunx oxfmt` on the four touched files; `bunx tsc --noEmit` clean; `bun run lint`
  (oxlint) clean; `bun run lint:eslint` only the pre-existing `project-card.tsx` `<img>`
  warning; dev server compiles `/projects/transcript` (200).
- Layout proof via a temporary no-auth probe under the real `AppShell` with the same
  classes, screenshotted in headless Chrome at **1920×949 scrolled 300px** (the geometry of
  the incident): sidebar full-height and stationary, header pinned, transcript pane capped
  with its own scroller, nothing overflowing. Probe deleted afterwards.
- `git diff HEAD -- web/src/components/layout/app-shell.tsx web/src/app/globals.css`: empty.

## Known limitation

The pane cap `min(70vh,36rem)` approximates "remaining height"; on short screens the page
itself scrolls normally (shell sticks, verified above). A hard "window never scrolls"
guarantee needs the shell to own scrolling — shelved deliberately, see the 1435 note
(a progress note written for the revert was lost; its content lives in the chat history and
the summary above).

## Next step

- Not committed. If you want it: the working tree has backend + contracts + UI ready to stage
  (`image.png` removal staged as `D`, `.gitignore` change included).
- Optional polish later: match prev/next navigation in Find, start-time-only editing stands
  (end times stay server-clamped), no DOC/PDF export.
