# Thumbnail studio: portrait video fit + multi-select (delete / redo / download)

## What I did

Two follow-ups from user feedback.

### 1. Portrait video preview no longer crops/zooms

A 9:16 upload was showing zoomed in the source-video card. Root cause: the player was
`fluid: true` with no fixed ratio, so once video.js resolved the media's dimensions it could size
the player taller than the card's fixed height (`WORKSPACE_PANE_HEIGHT`), and the clipped
overflow read as a zoom. Fix: pin the player to `aspectRatio: "16:9"` and add
`.studio-video .vjs-tech { object-fit: contain }` (plus `vjs-poster` contain) so any source is
letterboxed fully inside the box instead of cropped or stretched.

### 2. Multi-select on concepts (delete / redo / download)

- Each concept card has a selection checkbox (top-left; the Applied / version badges moved
  top-right). A toolbar above the grid has **Select all** and, once anything is selected,
  **Redo**, **Download**, **Delete**, and **Clear** with a live count.
- **Delete** — loops the existing per-concept delete.
- **Redo** — new batch endpoint: one `thumbnail` job in `regenerate` mode. Each selected concept
  keeps its headline, rationale and source moment and is re-rendered as a new version (a fresh
  take, not a new idea). The worker's `_generate_batch` gained a `regenerate` branch that builds
  the plan from the stored concepts and numbers the new version from the existing count; per
  concept aspect is honoured.
- **Download** — new endpoint returns a zip of the selected concepts' active images. The browser
  fetches it with auth headers (`apiFetchBlob`) and saves the blob, so it is a real download
  rather than N cross-origin tabs.
- 9:16 concept previews now use `object-contain` in the card instead of `object-cover`.

## Structural changes

- `contracts/openapi.yaml`: two paths (`/thumbnails/regenerate`, `/thumbnails/download`) and
  `ThumbnailSelectionRequest`.
- Backend: `schemas/thumbnails.py`, `services/thumbnail_service.py` (`regenerate`,
  `download_bundle`, `_slug`), `workers/thumbnail_worker.py` (regenerate branch, per-concept
  aspect/version), `api/thumbnails.py`.
- Web: `lib/api-client.ts` (`apiFetchBlob`), `lib/projects.ts` (`regenerateThumbnails`,
  `downloadThumbnailsZip`), `studio/thumbnail-panel.tsx` (selection UI),
  `source-video-player.tsx` + `video-player-skin.css` (portrait fit).

## Decisions and gotchas

- **Redo = new version, same idea.** Reusing the stored headline/rationale keeps a bulk redo
  coherent; it does not re-run the planner (that would change the concept). The reference frames
  are re-extracted, so a redo also picks up the anti-slop prompting.
- **Zip in memory.** `zipfile` is stdlib; the bundle is a few MB, so no temp file or new
  dependency. Empty selections yield an empty zip (the UI only calls it with ≥1).
- **Auth for binary.** Browser downloads cannot set headers on a plain navigation, so the zip is
  fetched as a blob through the API client and saved via an object URL.

## Verification (all run)

- Backend: `ruff` clean; `mypy app` clean (85 files); generated OpenAPI lists both new paths;
  contract YAML parses.
- Web: `tsc` clean; `oxlint` clean; `eslint` clean; `bun run build` succeeds.
- **Live (ADC, project `chicken curry`)**: `download_bundle` produced a 3.3 MB zip with both
  images; `regenerate` on one concept kept the headline + rationale and appended version 2 with a
  fresh critique (L/P/F 4/5/4) through the real worker.
- No tests added (repo policy).

## Not done / next step

- The video fix pins landscape; a future improvement could letterbox to the source ratio while
  letting the card grow, if portrait-first previews are wanted.
- Bulk download has no progress UI (a zip of a few MB is quick); a spinner/toast is enough for
  now.
