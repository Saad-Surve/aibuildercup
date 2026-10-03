# Header-tabs polish, workspace scroll, and video action row

## What I did

Refinements on top of the `headerTabs` flag and the video project pane (web only).

- **No header tabs on the project overview.** The studio only registers the header nav when a
  module other than `overview` is active. On the landing grid the six tiles already are the
  navigation.
- **Overview tab removed from the header strip** (`ModuleNav` gained `showOverview`); the
  remaining six tabs are centered in the header (the header slot is `justify-center`).
- **Active header tab is signal/pink.** The active tab gets a `signal`-coloured border and a
  signal-coloured icon, with no background fill; the label stays default. The in-page variant
  keeps the old filled `secondary` pill.
- **Tab switch no longer moves the page.** `useStudioModule.navigate` used to `window.scrollTo(0)`
  on every module change; with `headerTabs` on it now leaves the scroll position alone (the page's
  snap-proximity scroll was what made the whole page jump). Without the flag, behaviour is
  unchanged.
- **Delete / New revision row.** Delete moved to the left with `destructive` colours
  (`DeleteProjectDialog` gained a `destructive` prop), New revision moved to the right as the
  primary CTA (`NewRevisionButton` gained a `variant` prop).

## Structural changes

- Web only. `module-nav.tsx` (props + styling), `video-studio.tsx` (header registration +
  action row), `use-studio-module.ts` (scroll), `delete-project-dialog.tsx` + `video-revisions.tsx`
  (props), `app-shell.tsx` (center the header slot). No backend or contract changes.

## Verification

- `bunx tsc --noEmit` clean; `bun run lint` clean; `bun run lint:eslint` 1 pre-existing `<img>`
  warning; `bun run build` succeeds.

## Not done / next step

- If a very long tab strip ever overflows the header on small screens, switch to icons-only below
  `sm`; currently it scrolls horizontally.
