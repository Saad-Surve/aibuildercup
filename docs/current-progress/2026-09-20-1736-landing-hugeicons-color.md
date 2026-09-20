# Progress — 2026-09-20 17:36 IST

Status: **landing page, Hugeicons migration, colour pass, sticky sidebar, onboarding tweaks.
Committed and pushed.**

## 1. What I did

### Landing page (new `/`)

- `/` is now a landing page, not a redirect. Split layout with a vertical divider: left is the
  brand mark, tagline, and a colourful `HeroIllustration` (video frame + heatmap tracks); right
  is the sign-in panel.
- Removed the `(auth)/login` route and `login-page.tsx`. Extracted `SignInPanel` and the
  signed-in redirect into `LandingPage`. Guards and the profile delete flow now return to `/`.

### Hugeicons

- Installed `@hugeicons/react` + `@hugeicons/core-free-icons`. Removed `lucide-react` usage
  everywhere (our components **and** the shadcn primitives: select, dropdown-menu, sonner,
  spinner, checkbox). `components.json` `iconLibrary` is now `hugeicons`.
- Added `components/common/icon.tsx` (`Icon` wrapper) that standardises size and stroke width.
  The only remaining inline SVG is the Google brand mark on the sign-in button.

### Colour

- `--primary` is now the blue `signal` token, so buttons, progress, and badges carry colour
  instead of ink.
- Active nav, active onboarding step, selected chips, and the logo mark are coloured (logo uses
  blue/amber/red tracks — the heatmap motif). Landing hero uses the full severity palette.

### Fixes and tweaks

- **Sticky sidebar**: the aside is now `sticky top-0 h-[100dvh]` with an internally scrolling
  nav, so it stays put while the main column scrolls.
- Onboarding step count moved from the header to the bottom action row (right-aligned next to
  the buttons).
- Red asterisk on required fields (Creator name), with `aria-required`.

## 2. Verification

- `bun run build` clean: routes `/`, `/dashboard`, `/onboarding`, `/profile` (no `/login`).
- `oxlint` exit 0, `eslint` clean, `oxfmt` applied.
- Dev server: all routes 200, landing renders the tagline, no new runtime errors.

## 3. Gotchas

- `HugeiconsIcon` types `strokeWidth` as `number`, which conflicts with `React.ComponentProps<"svg">`
  (string | number). The `Spinner` takes only `className` now.
- `shadcn add` still prompts to overwrite existing files even with `-y`; pipe `n` to keep them.

## 4. Not done / next step

- Dashboard/project list + upload flow, then the transcript + heatmap workspace.
- `web/DESIGN.md` holds the updated component inventory.
