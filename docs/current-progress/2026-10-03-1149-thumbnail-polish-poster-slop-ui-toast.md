# Thumbnail polish: cover everywhere, less AI slop, tidier UI + toasts

## What I did

Follow-up polish on the thumbnail feature from `2026-10-03-1113`, from user feedback.

- **Applied thumbnail is now the project cover everywhere.** Applying a concept writes
  `posterStoragePath` (the active version's object) to the project document. `Project` gained
  `posterStoragePath` and a read-time `posterUrl` (signed). The API mints `posterUrl` in
  `GET /projects` and `GET /projects/{id}` (and PATCH) via `ProjectService.poster_url`; the
  project card prefers it over the locally captured frame poster, and the workspace
  `SourceVideoPlayer` uses it as the video poster. Revising an applied concept updates the
  poster to the new active version; deleting an applied concept clears it.
- **Removed the "use the hero model" toggle** from the panel (backend still accepts
  `useProModel`; the UI no longer offers it).
- **Anti-AI-slop prompting.** New `ANTI_SLOP` block appended to every generate and edit prompt in
  `thumbnail_worker`: photorealistic, natural skin/lighting, preserve the real face, and an
  explicit avoid-list (waxy skin, HDR, stock smiles, warped hands/faces, garbled text, extra
  objects, watermarks, flares).
- **UI alignment.** The thumbnail controls are now a single header row (aspect + concepts on the
  left, Generate on the right, labels inline) with the direction field below, instead of the
  ragged `items-end` row. Concept-card actions split into Edit/Use on the left and icon-only
  secondary actions (more-like-this, download, delete) on the right, so the row no longer wraps.
- **Toasts.** Moved to `bottom-right`; `ui/sonner.tsx` now styles the toast (rounded-xl, border,
  popover blur, shadow, title/description/action/close classes, 22rem width).

## Structural changes

- `contracts/openapi.yaml`: `Project` gains `posterStoragePath` + `posterUrl`.
- `schemas/projects.py`, `services/project_service.py` (field + `poster_url`, `url_ttl_seconds`),
  `api/projects.py` (`_with_poster`), `services/thumbnail_service.py` (apply/revise/delete sync).
- Web: `lib/types.ts`, `project-card.tsx`, `source-video-player.tsx`, `video-studio.tsx`,
  `studio/thumbnail-panel.tsx`, `app/layout.tsx`, `ui/sonner.tsx`.
- `workers/thumbnail_worker.py`: `ANTI_SLOP`.

## Decisions and gotchas

- **Sign on read, not in the service.** `ProjectService.get` is called for ownership checks on
  hot paths (thumbnail polling every ~3s). Minting a signed URL there would cause a signBlob
  round-trip per poll, so `posterUrl` is minted only in the API response layer, and only when
  `posterStoragePath` is set. The card/player skip their client-side frame capture when a cover
  exists.
- **Poster follows the active version.** `add_version` re-points `posterStoragePath` when the
  concept is applied, so a revise-after-apply updates the cover instead of leaving it stale.

## Verification (all run)

- Backend: `ruff` clean; `mypy app` clean (85 files). Generated OpenAPI `Project` has
  `posterUrl` + `posterStoragePath`.
- Web: `tsc` clean; `oxlint` clean; `eslint` 0 errors (one pre-existing `<img>` warning in
  `project-card`); `bun run build` succeeds.
- **Live (ADC, project `chicken curry`)**: re-ran `ThumbnailService.apply` →
  `posterStoragePath` = `.../thumbnails/{id}/v2.png` (the revised active version) and
  `ProjectService.poster_url` minted a URL; `_with_poster` (the exact API helper) returned a
  non-null `posterUrl`.
- No tests added (repo policy).

## Not done / next step

- The dashboard "recent projects" and any other cover surface read the same `Project.posterUrl`,
  so they are covered automatically; not separately re-checked in a browser.
- The signed `posterUrl` expires (~15 min); a card left open longer falls back to nothing until
  the next refetch. Acceptable, but a longer TTL or a proxy endpoint would remove the edge.
