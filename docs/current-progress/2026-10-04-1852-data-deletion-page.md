# Data deletion instructions page (Meta app requirement)

## What I did

Meta app review requires apps that access user data to give users a way to delete it (a data
deletion callback **or** public deletion instructions). Added the **instructions** route.

- **New** `web/src/app/data-deletion/page.tsx` (public, static, outside `(app)`) using the shared
  `LegalPage` shell. Sections: Overview, What we store, Delete your account, Delete a project or
  item, Disconnect a platform, Request deletion by email, What happens after deletion, Contact.
  - Instructions match the real flows: Profile → "Delete account" (`DELETE /me`, which revokes
    provider OAuth, deletes the user GCS prefix, then the Firestore tree); per-project delete in the
    project workspace; item deletes in their panels; Settings → Connections → disconnect.
  - Email fallback: mailto with subject "Data deletion request", ~30-day turnaround, ownership
    verification.
- `web/src/components/legal/legal-page.tsx`: footer now links Privacy / Terms / **Data Deletion**.
- `web/src/components/landing/landing-page.tsx`: footer **Legal** column adds **Data Deletion**.
- `web/src/app/privacy/page.tsx`: "Your choices and deletion" now links to `/data-deletion`.

## Verification

- `bunx tsc --noEmit` clean; `bun run lint` (oxlint) clean; `bun run lint:eslint` 0 errors
  (1 pre-existing `no-img-element` warning in `project-card.tsx`, untouched).
- `bun run build` clean; route table shows `○ /data-deletion` (static). `○ /privacy` and `○ /terms`
  still static.

## Decisions / gotchas

- Chose the **instructions URL** path, not a data deletion callback endpoint: no Meta connector exists
  yet, so a callback that verifies `signed_request` would be dead code. The self-serve flows are real
  today, so instructions are accurate. If a Meta connector ships, add a callback
  (`POST /api/internal/meta/data-deletion`) that verifies the signed request and returns a status URL
  with a confirmation code — see `contracts/events.md` / `contracts/openapi.yaml` first.
- Everything stays under `users/{uid}` and the user GCS prefix, so account deletion already covers
  all of it (no extra delete wiring).

## Not done / next step

- Deploy and register `https://habeas-codus.web.app/data-deletion` as the Data Deletion Instructions
  URL in the Meta app dashboard (Basic Settings → User Data Deletion).
- Register the privacy policy URL and terms URL alongside it.
- Optional: in-app link to `/data-deletion` from the Profile delete card.
