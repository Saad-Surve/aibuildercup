# Progress — 2026-09-20 18:12 IST

Status: **landing back to light mode, tightened to exactly one viewport with no scrollbars. Not
committed.**

## 1. What I did

- **Light mode everywhere.** `ThemeProvider` now defaults to `light` and uses a fresh
  `storageKey` (`resonance-theme`) so any previously stored dark/system preference is ignored.
  The user menu still offers Light / Dark / System.
- **Landing is light and fixed-height.** Removed the forced `dark` class; the hero uses theme
  tokens on a light background. `main` is `h-[100dvh] overflow-hidden` (was `min-h-[100dvh]`), so
  the page is exactly one viewport tall with no scrollbars.
- **Less top space.** Dropped the `py-20` padding (content is centred in the remaining space),
  reduced the gap, and shrank the logo plate.
- **Logo on light.** The supplied `logo.png` is a black lockup with a white wordmark, so on a
  light page it sits on a compact rounded dark plate (with `object-cover` trimming the lockup's
  own black margins). Faithful to the asset; legible on light.
- **Background converted to light.** Same restrained structure (coloured haze, glass panels at
  the edges, minimal floating circles, faint grain) but with light-appropriate colours; the
  white light-streaks were dropped since they are invisible on a light base.

## 2. Verification

- `bun run build` clean; `oxlint` exit 0; `eslint` clean; `oxfmt` applied.
- `/`, `/persona`, `/dashboard` return 200.

## 3. Notes

- The landing no longer follows the app's dark theme; it is always light, per the request. If a
  dark landing is wanted again later, it needs the dark background variant and a blend-mode logo
  treatment.
- If the browser still looks dark, hard-refresh once so `next-themes` picks up the new storage
  key.

## 4. Not done / next step

- User to eyeball the landing height/spacing and the light theme.
- Commit pending (not requested this turn).
