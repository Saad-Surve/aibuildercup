# Studio polish: path routes, snap, video card actions, live caption preview

## What I did

Ten follow-up changes to the studio/draft work from the previous note, plus a local commit
of that work (`cf8e9cb`).

1. **Module tabs hidden on overview.** `ModuleNav` only renders when a module is active, so
   the landing page is just the source video + module grid.
2. **Path-based module routes.** `/projects/view/project/{projectId}/{module}` (and
   `.../{projectId}` for overview) instead of `?projectId=&module=`. The web app is a static
   export, so arbitrary ids cannot be prerendered and a Next dynamic route is impossible
   (even in dev it demands the param in `generateStaticParams`). Instead the `/projects/view`
   shell is served for that prefix by a rewrite — `next.config.ts` `rewrites()` in dev and
   the Firebase Hosting rewrite in production — and the client reads the id/module from the
   path. Query-string links still work.
3. **Scroll snap fixed.** `globals.css` was `scroll-snap-type: y mandatory` despite a comment
   saying proximity; mandatory locked non-snapping tabs to the header. Switched to
   `proximity` and gave every module a snap wrapper (`lg:snap-start lg:snap-always
   lg:scroll-mt-20`), so all tabs snap level with the video.
4. **Edit next to the title.** `EditProjectDialog` gained an `iconOnly` trigger; the project
   header renders it beside the name.
5. **Video card actions moved below the card.** `VideoRevisions` (Revision badge, History,
   New revision) and `DeleteProjectDialog` now sit under the source-video card.
6. **Status pill moved into the video card header**, where the New revision button used to be.
7. **Live caption preview.** Removed the fake gradient `StylePreview` from the Burn Captions
   card. A new `CaptionPreviewProvider` lets the module drive a `CaptionOverlay` rendered
   over the actual source video (scaled to the real frame, karaoke included), only while the
   captions module is open.
8. **Validated number inputs.** Font size, distance from edge, and characters per line are now
   number fields with range validation (invalid values show an inline error and revert on
   blur). Outline width, box opacity, and shadow stay sliders.
9. **Captions card reorganized** into Preset / Typography / Colour & background sections in a
   two-column layout now that the preview is gone.
10. **Placeholder previews.** Packaging shows three hardcoded thumbnail mocks, two infographic
    clip mocks with charts, and a sample title/description/tags. Localization shows sample
    translations per target language and a waveform dubbing mock. Both are labelled
    "Sample preview".

## Changes

### Web

- `app/(app)/projects/view/page.tsx` — reads the path (`usePathname`) with query fallback;
  `next.config.ts` rewrite for `/projects/view/project/:path*` → `/projects/view`.
- `firebase.json` — matching Hosting rewrite → `/projects/view.html`.
- `components/projects/project-workspace.tsx` — takes `moduleId`, custom header (edit beside
  title), draft-only status/delete in the header.
- `components/projects/video-studio.tsx` — `moduleId` prop, tabs hidden on overview, status
  pill in the card header, revisions + delete below the card, `CaptionPreviewProvider`,
  per-module snap wrapper.
- `components/projects/studio/caption-preview.tsx` — new context + `CaptionOverlay`.
- `components/projects/source-video-player.tsx` — renders the overlay when a preview style is
  active.
- `components/projects/caption-burn-dialog.tsx` — context-driven style, `NumberControl`,
  reorganized layout, `nativeButton={false}` on the download link.
- `components/projects/studio/{module-nav,module-grid,packaging-module,localization-module}.tsx`
  and `edit-project-dialog.tsx`, `project-card.tsx`, `create-project-dialog.tsx`,
  `transcript-editor.tsx` — path links / new content.

### Docs

- `frontend-plan.md` — path routes, snap, caption overlay, sample previews.

## What I decided / discovered

- **Static export rules out dynamic path params.** `generateStaticParams` is validated at
  request time in dev too, so a catch-all cannot serve arbitrary ids. A rewrite to the static
  shell plus client path parsing is the only approach that keeps the path URL in dev and
  production; production links fall back to a hard navigation (the shell loads and reads the
  path).
- **Base UI `Button` needs `nativeButton={false}`** when `render` is an `<a>`/`Link`,
  otherwise it warns and drops native button semantics.
- The caption overlay is scoped to the captions module (the provider passes `null` style
  otherwise) so it does not linger on review/transcript.

## Verification

- `bunx tsc --noEmit` clean; `bun run lint` (oxlint) clean; `bun run lint:eslint` 0 errors
  (one pre-existing `<img>` warning); `bun run build` succeeds.
- Dev server: `/projects/view`, `/projects/view/project/{id}`, `.../{id}/review`, and
  `.../{id}/captions` all return 200, and the Base UI button warning is gone.
- No backend changes this pass; previous `ruff`/`mypy` results still hold.

## Not done / next step

- Committed `cf8e9cb` (studio + draft). This pass is **uncommitted**.
- Production link clicks to a project path do a hard navigation (static export limitation).
  If that matters, switch hosting to a Node/SSR target.
- The transcript editor still uses `/projects/transcript?projectId=…`; could move under the
  project path for consistency.
