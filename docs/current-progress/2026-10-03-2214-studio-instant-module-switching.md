# Studio: instant module switching + lazy module chunks

## What I did

Fixed the "every tab switch fires an API call" and slow/cold project-open behaviour.

- **Module tabs are no longer navigations.** `ModuleNav` and `ModuleGrid` used to
  `<Link>` to `/projects/view/project/{id}/{module}`, a path served only by a rewrite.
  Replaced with shallow client routing: a new `useStudioModule` hook keeps the active
  module in React state and mirrors it into the URL with `window.history.pushState`
  (the Next-documented SPA pattern; Next patches pushState to update `usePathname`
  via `ACTION_RESTORE`, with no RSC fetch and no remount). `renderModule` swaps in
  place, so React Query's cache and the realtime socket survive a tab switch.
- **Lazy-loaded the five heavy modules** (`module-registry.tsx`) with `next/dynamic`,
  plus hover/focus prefetch (`prefetchStudioModule`) so the chunk is usually warm by
  the time a tab is clicked. The overview no longer parses the thumbnail canvas,
  glossary editor and dubbing UI up front.
- **Stopped the transcript refetching on every remount.** `useProjectTranscript` had
  `staleTime: 0` + `refetchOnMount: "always"`, so every pane remount re-downloaded the
  transcript. Now `staleTime` is 60s once data exists (still 0 while missing) and
  mount uses the default stale check. Edits/versions/realtime events still invalidate.
- **Fixed workspace entry in the static export.** A client navigation to the
  rewritten `/projects/view/project/{id}` cannot find an RSC payload in the export
  (only `/projects/view.txt` exists), so it fell back to a full document load. The
  project card, create-project dialog and transcript back link now enter through the
  real route `/projects/view?projectId={id}` via `workspaceHref`; once inside, module
  switches still use the pretty path.

## Files

- `web/src/lib/studio.ts` — `isStudioModuleId`, `studioModuleHref`,
  `studioModuleFromPath`, `workspaceHref`.
- `web/src/hooks/use-studio-module.ts` — new; active module + pushState.
- `web/src/components/projects/studio/module-registry.tsx` — new; dynamic modules +
  prefetch.
- `web/src/components/projects/studio/module-nav.tsx` / `module-grid.tsx` — `<a>` +
  intercepted left click + `aria-label`.
- `web/src/components/projects/video-studio.tsx` — takes `activeModule` /
  `onModuleSelect`, uses the registry.
- `web/src/components/projects/project-workspace.tsx` — owns the module via the hook.
- `web/src/app/(app)/projects/view/page.tsx` — parses module via `studioModuleFromPath`.
- `web/src/hooks/use-project-transcript.ts` — conditional staleTime.
- `web/src/components/projects/{project-card,create-project-dialog,transcript-editor}.tsx`
  — entry links via `workspaceHref`.

## Decisions / gotchas

- `pushState` is the right primitive here (Next 16 docs, `single-page-applications.md`
  and `linking-and-navigating.md`). Verified in `next/dist/client/components/app-router.js`:
  it dispatches `ACTION_RESTORE` to sync `usePathname`/`useSearchParams` and does **not**
  fetch. Modifier-clicks and new tabs still use the real `href`.
- A static export has **no RSC payload for rewritten paths**. Any future link into a
  project must use `workspaceHref` (query on the real route), not the pretty path, or it
  will hard-reload in production. The pretty path is only safe for pushState, new tabs,
  and reloads (Firebase rewrite serves the shell).
- `refetchOnMount: "always"` is a trap for pane-based UIs; avoid it.
- No tests (project rule). Verified with `tsc`, `oxlint`, `eslint` (0 errors, 1
  pre-existing `<img>` warning), and `next build`.

## Running in the background

- Backend: `uv run uvicorn app.main:app --reload --port 8080` → `.logs/backend.log`
  (`/api/healthz` 200).
- Web: `bun dev` → `.logs/web.log` (http://localhost:3000, 200).
- Restarted the stale dev server that was holding port 3000.

## Not done / next step

- Not verified in a real browser (no click-through); the pushState behaviour is
  confirmed from the Next source and the dev server responses.
- Optional: prefetch module chunks on `requestIdleCallback` after the workspace loads,
  and parallelise the project + assets + transcript fetches (currently project first,
  then assets/transcript).
