# Landing session — 2026-09-20 (21:17 → 23:39 IST, consolidated)

One note for the whole landing arc. It supersedes and replaces these twelve
notes, which were merged into it and deleted:
`2117-landing-creator-vignettes`, `2127-me-404-vignette-motion`,
`2141-landing-longform-static`, `2202-landing-pill-bento-orbit`,
`2217-landing-compact-brands`, `2237-landing-interactive-demos`,
`2243-flow-elbows-bento-tweaks`, `2302-stub-pulses-hover-demos`,
`2309-pulse-cycle-hover-auto`, `2325-card-hover-remount`,
`2326-parallel-stubs`, `2332-flow-orchestration`.
Older notes (≤2045) are untouched. Not committed.

## 1. Auth fix that fell out of this session

- Sign-in failed with `GET /me 404`: local `web/.env.local` had
  `NEXT_PUBLIC_API_BASE_URL=http://localhost:8080` (missing `/api`; the
  contract serves `/api/me`). Fixed + hardened: `api-client.ts` gained
  `normalizeApiBaseUrl()` (appends `/api` when missing), `mocks/handlers.ts`
  imports the shared `API_BASE_URL`, `.env.local` corrected (restart dev
  server to pick it up).

## 2. Hero backdrop

- Empty glass rectangles replaced with two mirrored peripheral vignettes
  (review-timeline card left, short-clip card right) + waveform sculpture +
  export chip, all static (ambient loops removed per request).
- VO waveform contrast fixed (solid sky-700/violet-700/amber-600).
- Motion rule for the page: nothing self-runs except explicitly requested
  pieces, all reduced-motion-gated; the rest is scroll/hover/drag/click.

## 3. Page structure (long-form)

- Sticky full-width bar replaced by a scroll-condensing pill nav
  (IntersectionObserver, `1fr/auto/1fr` grid so links stay exactly centred,
  compact logo in pill mode). Page owns its scroll container with hidden
  scrollbar chrome (`.no-scrollbar`, `scroll-smooth`).
- Sections: hero (serif headline, Google CTA, secondary anchor) →
  capability strip → platforms flow → feature bento → dotted 3-step workflow
  → gradient CTA (`Start creating`) → footer with force-fit SVG outline
  wordmark (`textLength` + `lengthAdjust="spacing"`, contained to footer
  width). Signed-in users short-circuit to a loading screen.
- Type: Schibsted Grotesk replaced Geist app-wide (`font-sans`/`heading`);
  mono + Playfair unchanged. `DESIGN.md` documents the landing exception.

## 4. Platforms flow (current state)

- Image-2-style stage (desktop; stacked fallback on mobile): derivative
  chips → centre studio tile (`logo-mark.png` + Connected) → five brand
  destinations using the original `public/` SVGs (Instagram, TikTok, YouTube,
  X, Facebook; LinkedIn/Medium/Substack in an `Also ships to` row).
- Connectors are static dotted-gray rectangular elbows. Animation is ONE
  master rAF timeline (`useFlowStage`, 6.5s loop): inputs arrive Short clip →
  Captions → Blog draft (0–2.1s), centre scales 1.00→1.02→1.00 with a
  restrained glow (2.1–2.6s), outputs distribute top-down (2.6–5.6s), calm
  settle, seamless restart. Packets are HTML dots positioned per frame via
  `path.getPointAtLength` mapped container-relatively (no screen matrices —
  an earlier `getScreenCTM` mapping left the stage blank and was replaced).
  easeInOutCubic pacing, fade envelopes, brand/source colours with glow.
  Idles offscreen, never runs under reduced motion.
- Rejected along the way: orbit rings + satellite icons, simultaneous
  multi-pulse loops, sequential CSS-delay cycles, static coloured stubs.

## 5. Bento (current state)

- Six cards, asymmetric rhythm, one light surface (`shadow + ring +
  border-transparent`), no card icons, `text-xl` titles with per-card hover
  accents (emerald/amber/rose/indigo/fuchsia/sky), no hover elevation.
- Hands-on demos, all triggered by hovering the CARD (state lifted to the
  article; demos remount with `key` on leave so every state resets):
  draggable heatmap cursor with positional feedback pills (2 rows, slow tour
  on hover), realistic SRT block (cue highlight cycles on hover), hot-zone
  clip cutter (auto-cuts on hover, manual Cut/Reset), EN→HI translation
  stepper (auto-flips on hover, manual steps), send→typing-dots→reply chat
  (auto-sends on first hover, manual composer), Draft→Edit→Final triple pages
  with dotted arrows (bars replay entrance on hover).
- Pointer cursors on all buttons (base `Button` primitive included).

## Verification (final state)

- `bun run build` clean, `oxlint` exit 0, `oxfmt` clean (a `set-state-in-effect`
  round was resolved via remount-keys + mount initializers; the one article
  a11y flag carries a scoped block-disable since hover is preview-only).

## Open / next

- Eyeball the 6.5s flow story end to end after a dev-server restart +
  hard refresh; confirm packet pacing, glow restraint, centre pulse, loop seam.
- Possible later: scroll reveals, real platform-connect wiring,
  testimonials/pricing. Commit pending (not requested).
