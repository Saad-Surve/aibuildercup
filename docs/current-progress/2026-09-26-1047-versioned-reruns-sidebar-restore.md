# Progress — 2026-09-26 10:47 UTC — versioned re-runs, sidebar restored, header alignment

## Header alignment fixed
- The previous `items-baseline` + `self-center` change was what pushed the icons out of line. All
  three card headers (Review / Transcript / Findings) are back to `items-center` with the meta at
  `text-sm`, so the icon, title, divider and meta-line all sit on one axis.

## Sidebar restored
- Reverted the `hideRail` change: the nav rail is shown on every page again, including
  `/projects/view`.

## Versioned re-runs (dropdown per card)
- **Backend**
  - `TranscriptService.list_versions` returns every saved generation (oldest first:
    `transcriptId`, `version`, `language`, `durationMs`, `wordCount`, `createdAt`).
  - `TranscriptService.get(..., version=N)` loads a specific generation (falls back to the active
    one when omitted).
  - `GET /api/projects/{projectId}/transcript?version=N` and
    `GET /api/projects/{projectId}/transcript/versions`. Contract + schemas updated.
- **Web**
  - `listTranscriptVersions()` / `getTranscript(projectId, version?)`; `useProjectTranscript`
    takes a `version` and only polls the active one.
  - Transcript card: a `v1`/`v2`/`v3`… `Select` next to the title, plus the "Run transcript again"
    button. Picking a version pins that generation; a rerun resets back to active.
  - Review card: the run picker is now labelled `v1`/`v2`/`v3`… (was "Run N") and appears as soon
    as a run exists.
- Findings follow the selected review run (they are part of it), so they need no separate picker.

## Verified
- Backend: `ruff` clean, `mypy` clean.
- Web: `tsc --noEmit` clean, `oxlint` clean, `next build` passes.
