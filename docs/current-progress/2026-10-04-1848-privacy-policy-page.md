# Public privacy policy page

## What I did

Added a public **`/privacy`** route so the studio has a citable privacy-policy URL (needed for
third-party / Meta app review).

- `web/src/app/privacy/page.tsx` — server component, **outside** the `(app)` auth group, so it
  renders without sign-in. Static, prerendered (`○`) in `next build`.
  - Sticky brand header (Logo → `/`, "Back to home"), on-brand haze background, article body, and a
    small footer.
  - On-screen table of contents (lg+, sticky) with anchor links to 15 sections: Overview,
    Information we collect, How we use information, AI processing, When we share information,
    Connected platforms, Cookies and local storage, Data retention, Your choices and deletion,
    Security, International transfers, Children's privacy, Your privacy rights, Changes, Contact.
  - Content written to match the app's real data practices: Google sign-in (Firebase Auth), uploaded
    video + generated artifacts in GCS/Firestore, platform OAuth (generic — no Meta named), Google
    Cloud AI processing (Gemini/Vertex, STT, TTS, Translation, image gen), no ad trackers, and the
    real (not soft) project/account delete. No payments collected.
  - Contact email is `aibuildercup@gmail.com` (per user).
- `web/src/components/landing/landing-page.tsx` — footer now has a **Legal → Privacy Policy** column
  and a Privacy Policy link in the bottom bar, so crawlers/users can find it from the public home.

## Verification

- `bunx tsc --noEmit` clean; `bun run lint` (oxlint) clean; `bun run lint:eslint` 0 errors
  (1 pre-existing `no-img-element` warning in `project-card.tsx`, untouched).
- `bun run build` clean; route table shows `○ /privacy` (static).

## Decisions / gotchas

- Kept the policy **platform-generic** (user preference) — no Meta/Facebook/Instagram named, so it
  also stays true if no Meta connector ships.
- Public route deliberately lives at `web/src/app/privacy/` and not under `(app)`, so it is exempt
  from `RequireAuth`/`RequireOnboarded`. The root layout's `AuthProvider` still wraps it (harmless).
- No API/contract change, so `contracts/` was not touched.
- Contact email `aibuildercup@gmail.com` and the "last updated" date are inline constants at the top
  of the page — update them when the legal entity/domain is finalized.

## Not done / next step

- A **Terms of Service** page is not written yet (footer has a "Legal" column ready for it).
- Consider hosting the policy on the production origin (`habeas-codus.web.app`) before submitting the
  URL to Meta; the local path is `/privacy`.
- If a Meta/Instagram connector is added, extend "Connected platform data" / "Connected platforms" to
  name Meta explicitly and the scopes used.
