# Settings page, bento grid, and the header-tabs feature flag

## What I did

Follow-up UI work on the YouTube connector/publishing feature.

- **Connections moved to Settings.** New `/settings` page (sidebar item enabled) holds the
  `YouTubeConnections` card plus a **Feature flags** section. The card was removed from Profile.
  The temporary `/connections` page/route and its sidebar entry were deleted so there is one home.
  The publish module keeps its inline channel picker.
- **Bento grid is now 2×3.** `module-grid.tsx` no longer features the transcript card full-width;
  all six modules (Transcript, Review, Burn Captions, Thumbnail/Clips/SEO, Localization, Publish)
  render as equal tiles in a 2-column, 3-row grid.
- **Module card reflow.** The description now sits below the icon and title row and spans the full
  card width (starting at the extreme left), instead of being indented under the title.
- **`headerTabs` feature flag.** A toggle in Settings writes to a `localStorage`-backed store
  (`lib/feature-flags.tsx`, read with `useSyncExternalStore`). When on, the studio module tabs are
  rendered into the app's top sticky header via a `HeaderNavProvider` slot
  (`lib/header-nav.tsx`); the in-page tab strip and its `border-b` divider are hidden. When off,
  behaviour is unchanged. The `ModuleNav` gained a `variant="page" | "header"` prop.
- New `components/ui/switch.tsx` (Base UI switch) for the toggle.

## Structural changes

- Web only. New route `/settings`; removed `/connections`.
- Sidebar `Settings` is now `ready: true`; the `Connections` nav item was removed.
- New `lib/feature-flags.tsx` (global external store, no provider) and `lib/header-nav.tsx`.
- Header in `app-shell.tsx` now has a center slot (`headerNav`) between the logo and the user menu.

## Decisions / gotchas

- Feature flags persist in `localStorage` (`hc-feature-flags`) — instant, offline, per-browser.
  The registry shape makes moving them to server-side user preferences a call-site-free change.
- Header nav is a **ReactNode slot** the page fills, so the shell stays ignorant of studio modules.
- `useSyncExternalStore` avoids SSR/hydration mismatch (server snapshot = frozen defaults) and the
  oxlint `set-state-in-effect` rule.

## Verification

- `bunx tsc --noEmit` clean; `bun run lint` (oxlint) clean; `bun run lint:eslint` 1 pre-existing
  `<img>` warning; `bun run build` succeeds with `/settings` as a route and no `/connections`.
- Backend untouched this round.

## Not done / next step

- Optionally persist feature flags on the user document (`users/{uid}.preferences.featureFlags`)
  so they follow the account across devices.
- The header tab strip can overflow on very narrow screens; it scrolls horizontally. Could switch
  to icons-only below `sm` if that reads better.
