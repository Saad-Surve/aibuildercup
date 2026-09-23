# Progress — 2026-09-23 14:55 UTC — workspace updates without a manual refresh

A real upload transcribed correctly (Hindi/Hinglish, 1161 words, 84 segments, VTT+SRT) but the
workspace stayed stuck on "Transcribing…" until the user manually reloaded.

## Cause (client-side, not the pipeline)

React Query pauses `refetchInterval` when the tab loses focus (`refetchIntervalInBackground`
defaults to `false`), and the app had `refetchOnWindowFocus: false` globally. So while the user
was on another tab the job/project/transcript queries stopped polling, and nothing refetched when
they returned — the panel only updated on a reload. Access logs confirmed sparse polling
(14:43:50 → 14:44:29 → 14:45:39) and a single transcript fetch at 14:51:47 after the reload.

## Fix (`web/`)

- `providers.tsx`: `refetchOnWindowFocus: true` — stale queries refetch when the tab regains
  focus, so a finished transcription appears on return.
- `project-workspace.tsx`: `refetchIntervalInBackground: true` on the project and job queries so
  progress keeps updating while the tab is backgrounded. (Left off the transcript query to avoid
  polling forever after a failed transcription; the focus refetch covers it.)

Lint + build pass.
