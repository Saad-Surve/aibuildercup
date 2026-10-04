# Terms of Service page + shared legal layout

## What I did

Added a public **`/terms`** route and refactored both legal pages onto one shared shell.

- **New** `web/src/lib/legal.ts`: `LEGAL_CONTACT_EMAIL` + `LEGAL_LAST_UPDATED` in one place (the
  privacy page's inline constants moved here).
- **New** `web/src/components/legal/legal-page.tsx` (server components): `LegalPage` (sticky branded
  header, hero with "Legal" eyebrow / title / intro / "last updated", responsive on-page nav, article
  body, footer with Privacy + Terms links) and `LegalSection` (anchored `h2` + body). This is the only
  copy of the legal chrome; both routes compose it.
- `web/src/app/privacy/page.tsx` rewritten to use the shell (content unchanged).
- **New** `web/src/app/terms/page.tsx`: 16 sections — Acceptance, The Service, Eligibility and
  accounts, Your content, Acceptable use, Connected platforms, AI-generated output, Our intellectual
  property, Fees, Disclaimers, Limitation of liability, Indemnification, Suspension and termination,
  Governing law, Changes, Contact. Platform-generic (no Meta named). Notable clauses: you keep
  ownership of Your Content with a narrow processing license; AI output may be inaccurate and the
  studio (including its "legal" reviewer) is **not** professional advice; free while in development;
  liability capped at the greater of fees paid or US$100.
- `web/src/components/landing/landing-page.tsx`: the footer's **Legal** column now lists both Privacy
  Policy and Terms of Service.

## Verification

- `bunx tsc --noEmit` clean; `bun run lint` (oxlint) clean; `bun run lint:eslint` 0 errors
  (1 pre-existing `no-img-element` warning in `project-card.tsx`, untouched).
- `bun run build` clean; route table shows `○ /privacy` and `○ /terms` (both static).

## Decisions / gotchas

- Both legal routes stay outside `(app)` (public, no auth). `LegalPage` is a server component, so the
  pages remain statically prerendered.
- "Governing law" is intentionally neutral ("the jurisdiction in which the operator is established")
  because no legal entity/jurisdiction is decided yet. **Fill this in** if/when the entity is formed.
- Contact email and revision date live only in `web/src/lib/legal.ts` now.

## Not done / next step

- Deploy and use the production URLs for platform review, e.g.
  `https://habeas-codus.web.app/privacy` and `.../terms`.
- If a Meta/Instagram connector ships, name Meta and its scopes in both pages' connection sections.
- Optional: add `Policy` / `Terms` links to the in-app user menu or settings for logged-in users.
