# Progress — 2026-09-25 08:40 UTC — Player aspect fit, language names

Uncommitted (not requested — commit only on ask). No backend changes.

## Dead space under the video

- Root cause: video.js fluid mode defaults to a 16:9 box no matter what the
  file is. Any other aspect ratio left a dead gap inside the card that read
  as extra bottom padding.
- Fix: on `loadedmetadata` (plus once at setup) the player reads the
  `<video>` tag's intrinsic dimensions and calls `aspectRatio("w:h")`, so
  the box always hugs the content exactly — consistent padding on all sides
  for any ratio. Done through the element ref, no player internals.

## Language codes → names

- `languageLabel` now resolves regional STT codes: exact match first
  (`en` → English), else base + region (`en-US` → English (US)), else the
  raw code. Applied everywhere a code leaked into UI: project card footer
  and the transcript header (which showed both `en` and `en-US`).

## Verification

- Web: `oxlint`/`oxfmt` clean, `eslint` 0 errors (1 pre-existing `<img>`
  advisory), `bun run build` passes (confirms the video.js `aspectRatio`
  typing).

## Next

- Caption `<track>` from transcription; backend-generated `thumbnail` assets;
  per-card delete menus; Audience/Connections/Settings pages (unchanged).
