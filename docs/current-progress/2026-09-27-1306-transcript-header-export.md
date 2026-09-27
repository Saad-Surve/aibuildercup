# Transcript card header + export menu

## What I did

- **Removed the meta line** (`N segments · <language> · N speakers`) from the Transcript
  card header in `web/src/components/projects/transcript-panel.tsx`.
- **Moved the version (`v1`/`v2`) Select** into that vacated slot, directly after the
  `Transcript` title. It was previously grouped on the right with the action buttons.
- **Fixed the version dropdown width**: `SelectContent` now takes `className="min-w-0"`, so
  the popup matches the trigger width instead of the shared `min-w-36` minimum (the options
  were wider than the `w-20` trigger).
- **Added an Export dropdown** next to `Run transcript again` (`FileExportIcon` + chevron).
  New file: `web/src/lib/transcript-export.ts` with client-side serializers and a Blob
  download. Formats: SRT, VTT, TXT, Markdown, CSV, JSON. Each menu click downloads the file
  and fires a `sonner` success toast.
- Passed `projectName={project.name}` from `project-workspace.tsx` into `TranscriptPanel` so
  export filenames are slugged from the project name (`my-project-v2.srt`), falling back to
  `transcript-<projectId8>`.
- Added `.logs/` to the root `.gitignore` (background dev-server logs).

## Structural notes

- `TranscriptPanel` gained an optional `projectName?: string` prop. No contract/API change:
  export is entirely client-side, no new endpoint.
- Speaker chips (`S{n}`) in the segment list are unchanged; only the header summary text was
  removed. `speakerCount`/`showSpeakers` are still used by the list.
- The export menu uses the shared `DropdownMenu` primitive; it relies on the base
  `min-w-32` default rather than a custom width, to keep the popup tight.

## Decisions / gotchas

- No PDF/DOC serializer: there is no PDF or document library in `web/package.json`. Exports
  are text formats that can be opened by Word/Pages or printed to PDF. Adding DOC/PDF would
  mean a new dependency; not done.
- `oxfmt` rewrites CRLF working-tree files to LF on Windows (`core.autocrlf=true`). Running
  `bun run format` repo-wide would touch ~34 files that only differ by line endings — I
  formatted only the files I changed. `format:check` still reports the pre-existing set.
- Web dev server was already running on :3000 (PID 21560) before this session; backend on
  :8080. Both were used for verification (page compiles, `/api/healthz` ok).

## Verified

- `bunx tsc --noEmit` clean.
- `bun run lint` (oxlint) clean.
- `bun run lint:eslint` — 1 pre-existing warning in `project-card.tsx` (`<img>`), unrelated.
- Next dev compiled the workspace route with no errors.

## Not done / next step

- Not committed (user asked to hold commits).
- Optional: DOC/PDF export if a dependency is acceptable, or a server-side export endpoint.
- The `2026-09-26-1640-ui-polish-scrollbars-dark-theme.md` note in this folder is still
  untracked from a previous session and was not touched.
