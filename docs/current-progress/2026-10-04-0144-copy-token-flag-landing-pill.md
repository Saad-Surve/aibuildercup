# Copy-auth-token flag + landing pill button

## What I did

- **Landing header Sign in button.** When the landing header condenses into its pill
  (`condensed`), the `Sign in` button now takes `rounded-full` too, matching the pill. It keeps the
  default radius when the header is transparent.
- **New `copyAuthToken` feature flag (default on).** When enabled, a ghost key-icon button renders
  immediately before the avatar in the app header. Clicking it reads the current Firebase ID token
  and copies the whole `Bearer <token>` string to the clipboard, with a success toast (and an
  error toast if the write fails). New component `components/layout/copy-token-button.tsx`.
- **Both flags default on.** `headerTabs` default changed from off to on; `copyAuthToken` added
  with default on. (A stored `hc-feature-flags` value still wins over the default.)

## Structural changes

- `lib/feature-flags.tsx` (flag registry + defaults), `components/layout/copy-token-button.tsx`
  (new), `components/layout/app-shell.tsx` (render the button before `UserMenu` behind the flag),
  `components/landing/landing-page.tsx` (pill button radius). Web only.

## Verification

- `bunx tsc --noEmit` clean; `bun run lint` clean; `bun run lint:eslint` 1 pre-existing `<img>`
  warning; `bun run build` succeeds.

## Not done / next step

- Not committed this round (the user asked only for the change). Ready to commit.
