# Calendar review round 2: no title field, named selects, week height, platform logos, no manual linking

## What I did (web only, no contract/backend change)

- **Title field removed.** The slot dialog no longer asks for a title at all. A new
  slot takes the upload title when scheduled from one, else the project name
  (`initialTitle` → fixed `projectName` prop → picked project's name →
  "Untitled slot"). Edits keep the stored title; the edit dialog shows it as a
  read-only line for context.
- **Selects show names, not ids.** Project, status, and platform selects now map
  the stored value to its label via `SelectValue` function children (same pattern
  as `create-project-dialog`), so the picker never displays a raw project id or
  `scheduled` in lowercase.
- **Week view keeps month height.** The week grid has `min-h-[36rem]` so switching
  month ↔ week no longer collapses the calendar, and week cells show up to 8 slots
  before "+n more".
- **Platform is a dropdown with SVG logos.** New shared
  `components/calendar/platform.tsx`: `PLATFORM_OPTIONS` (YouTube, Instagram,
  TikTok, X, Facebook, LinkedIn — values match the onboarding vocabulary),
  `platformLabel`/`platformLogoSrc` (unknown values fall back to raw text /
  `globe.svg`, `youtube_shorts` maps to the YouTube mark), and `PlatformLogo`
  (`next/image`, like the landing page). Logos also appear on month chips, the day
  agenda, the Upcoming rail, and the project schedule rows.
- **No manual upload linking.** The "Linked upload" select is gone from the dialog.
  Linking stays fully automatic: a publish with `publishAt` creates its slot, and
  the project-side "Schedule" button still pre-links silently via the hidden
  `initialPublishId` (never presented as a choice). Edit mode shows a read-only
  "Linked upload · …" line from the slot's own data; the dialog no longer fetches
  the publish list.

## Verification

- `bun run lint` clean; `bun run lint:eslint` 0 errors (pre-existing `<img>`
  warning only — the new logo uses `next/image`); `bun run build` clean;
  dev `/calendar` serves 200.

## Not done / next step

- Same as before: authenticated end-to-end pass with a signed-in session.
