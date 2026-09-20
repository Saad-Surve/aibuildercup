# Progress — 2026-09-20 17:45 IST

Status: **persona editing from Profile and a premium centered landing page. Not committed yet.**

## 1. What I did

### Persona editing (Profile → steps, prefilled)

- `OnboardingFlow` now takes `mode: "onboarding" | "edit"`. In edit mode it drops the Welcome
  step, starts at Identity, prefills every answer from `GET /onboarding`, and the final button
  returns to `/profile` instead of `/dashboard`.
- `StepRail` takes the step list as a prop so edit mode shows the correct count.
- `DoneStep` has an edit variant ("Your persona is updated" / "Back to profile").
- New route `(onboarding)/persona/page.tsx` → `/persona`, wrapped in `RequireOnboarded`, renders
  `OnboardingFlow mode="edit"`.
- `ProfilePage`: the Creator persona card now has an **Edit persona** action (shown once a
  persona exists) that routes to `/persona`.

### Premium landing page (`/`)

Replaced the split layout with the briefed design:

- Centered hero: serif headline **"Create Without Limits"** (Playfair Display), sans subheadline
  "Your all-in-one creative studio for artists, filmmakers & digital creators", and the Google
  sign-in CTA below.
- `LandingBackground`: soft light rays, coloured bokeh, floating translucent geometry, and a
  film-grain layer. Motion is gated behind `motion-safe:`.
- `GoogleSignInButton` restyled to the brief: rounded pill, soft white background, subtle
  elevation, official Google "G" on the left.
- Added Playfair Display via `next/font` (`--font-playfair`) and mapped it to `font-serif` in
  `globals.css`; added `float` / `drift` / `rays` keyframes and the `.grain` utility.
- Removed `sign-in-panel.tsx` and `hero-illustration.tsx` (folded into the landing).

## 2. Verification

- `bun run build` clean: `/`, `/dashboard`, `/onboarding`, `/persona`, `/profile`.
- `oxlint` exit 0, `eslint` clean, `oxfmt` applied.
- All routes return 200; no fresh runtime errors (earlier log lines were transient HMR noise).

## 3. Notes

- The landing is a deliberate exception to the product-UI rules (documented in `web/DESIGN.md`):
  display serif + atmosphere are marketing-only and must not leak into the app.
- The landing headline is client-rendered (auth state resolves first), so it is not in the SSR
  HTML.

## 4. Not done / next step

- User to eyeball the landing and the persona edit flow in the browser.
- Commit pending (not requested this turn).
- Next build: dashboard/project list + upload flow, then the transcript + heatmap workspace.
