# Progress — 2026-09-20 18:02 IST

Status: **landing refined (logo + background), persona step rail clickable, sticky header with
avatar, brand renamed to Resonance. Not committed.**

## 1. What I did

### Landing refinement (no layout/typography/hierarchy changes)

- The landing is now a forced-dark surface (`dark` class on `<main>` + explicit charcoal base),
  independent of the app theme, to match the near-black/charcoal direction.
- Replaced the drawn mark with the supplied `public/logo.png` above the headline, using
  `mix-blend-screen` so the logo's black background dissolves into the page. Proportions
  preserved, no redraw.
- `LandingBackground` rebuilt with restrained, art-directed elements: deep charcoal base, a soft
  centre lift, warm-amber / muted-violet haze at the edges, two ambient light streaks, three
  translucent glass panels with simple rounded corners pushed to the periphery, four minimal
  floating circles, film grain, and an edge vignette. Removed the previous floating rounded
  squares that read as random UI shapes.
- Headline, subtitle, CTA, spacing, and composition are unchanged.

### Brand text

- "Habeas Codus" → "Resonance" in UI only: the `Logo` wordmark (now Resonance / Creator Helper
  Studio), the landing footer, and the document title. Docs/backend untouched.

### `/persona` and onboarding fixes

- `StepRail` is now clickable: each step is a button that jumps directly to it. The current
  step's answers are saved first, and the persona is generated if you jump to the Persona/Done
  step before it exists.
- The flow header is now `sticky` with a blurred background and shows the `UserMenu` avatar on
  the right (previously logo only, not sticky).

### Dark theme icon

- User menu dark theme now uses `Moon02Icon`.

## 2. Verification

- `bun run build` clean (`/`, `/dashboard`, `/onboarding`, `/persona`, `/profile`).
- `oxlint` exit 0, `eslint` clean, `oxfmt` applied.
- `/logo.png` served (image/png); all routes 200; no "Habeas" strings remain in `src/`.

## 3. Notes

- The landing stays a marketing exception (documented in `web/DESIGN.md`): forced dark, serif
  headline, atmospheric background. The app itself remains theme-aware.
- `public/logo-transparent.png` exists but has a light background, so `logo.png` + blend mode was
  the right choice for the dark hero.

## 4. Not done / next step

- User to eyeball the landing and the persona rail/header in the browser.
- Commit pending (not requested this turn).
