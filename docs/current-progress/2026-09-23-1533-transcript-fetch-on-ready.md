# Progress — 2026-09-23 15:33 UTC — transcript now loads as soon as the project is ready

Follow-up to `2026-09-23-1455`. A second upload (project `189421f0…`) showed the transcript card
stuck again. The pipeline was fine: project `ready`, `activeTranscriptId` set, 84 segments,
`GET /transcript` → 200.

## Root cause (client)

React Query's interval only fires when the tab is focused:
`queryObserver.js` → `if (this.options.refetchIntervalInBackground || focusManager.isFocused())
executeFetch()`. The project/job queries had `refetchIntervalInBackground: true`, so they kept
polling to `ready` while the tab was in the background, but the **transcript query did not**, so it
stayed paused on its stale 404. Access logs matched exactly: the project polled every ~4s while the
transcript made no requests, then fetched once at 15:18:48 when the tab regained focus
(the `refetchOnWindowFocus` fix from the previous note working).

## Fix (`web/`)

`project-workspace.tsx`: when the (background-polled) project status becomes `ready`, invalidate
the transcript query so it fetches immediately — no reload or refocus required. Kept the
transcript query's own interval off-background so a failed transcription cannot poll forever.

Lint + build pass.
