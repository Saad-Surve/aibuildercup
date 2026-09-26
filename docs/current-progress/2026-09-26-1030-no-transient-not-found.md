# Progress — 2026-09-26 10:30 UTC — stop transient "not found" flashes

## Problem
While the pipeline was still running (transcript/analysis/review loading), the workspace briefly
resolved to not-found/"unavailable" states and then recovered once data arrived.

## Cause
- `project-workspace.tsx` gated the whole workspace on `projectQuery.isError || !data`. During the
  processing poll (`refetchInterval` every 3s), any single failed refetch flips `isError` to true
  even though React Query still holds the last good `data`; the UI then rendered "Project not
  found" until the next poll succeeded.
- `transcript-panel.tsx` showed "Transcript unavailable" for any non-404 error, including a
  transient error mid-processing.

## Fix
- Workspace now shows "Project not found" only when there is genuinely no data (`!projectQuery.data`).
  Cached project data keeps the workspace rendered through refetch errors.
- Transcript panel only treats an error as unavailable once processing has stopped
  (`error && !notReady && !processing`); while the worker runs it keeps the progress state, and the
  next poll replaces it.

## Verified
- Web: `tsc --noEmit` clean, `oxlint` clean, `next build` passes.

## State
- Committed locally only (not pushed), per request.
