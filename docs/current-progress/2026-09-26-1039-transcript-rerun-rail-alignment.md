# Progress — 2026-09-26 10:39 UTC — transcript rerun, full-bleed workspace, header alignment

## "Run transcript again"
- Backend: new `AssetService.retranscribe_source` — finds the project's source video, verifies the
  object, and mints a NEW transcribe job keyed `transcribe-{project}-{asset}-r{version}` (the
  project's transcript version counter + 1). Re-completing the upload only returns the original
  idempotent job, so this is what makes a regeneration possible; a double-click before the new
  transcript lands maps to the same key.
- API: `POST /api/projects/{projectId}/transcript/retranscribe` → 202 `AcceptedJob`, schedules the
  worker exactly like upload-complete. Contract updated.
- Web: `retranscribeTranscript()` in `lib/projects.ts`; the Transcript card header has a
  "Run transcript again" button (`SparklesIcon`), disabled while processing, and invalidates the
  project + transcript queries so the pipeline card and polling take over.

## Full-bleed project workspace
- `AppShell` hides the nav rail on `/projects/view` (`hideRail`), so the header avatar no longer
  shifts when the rail collapses/expands and the two panes get the full width. The page still
  scrolls normally (window scroll); only the rail is removed.

## Card header alignment
- Review / Transcript / Findings title rows now use `items-baseline` (icon + divider set to
  `self-center`) and the meta line is `text-sm`, so "16 of 16 observations, worst first." lines up
  with "Findings" instead of sitting low.

## Also included (previously committed locally)
- `874ddc4` — stop transient "not found"/"unavailable" flashes during processing.

## Verified
- Backend: `ruff` clean, `mypy` clean.
- Web: `tsc --noEmit` clean, `oxlint` clean, `next build` passes.
