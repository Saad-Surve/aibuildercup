# Read-only demo account (seeded, hard-enforced, UI-disabled)

## What I did

Added a shared, read-only demo account and made it genuinely read-only.

- **Seeded demo user.** Created Firebase Auth user `demo@habeascodus.app`
  (UID `demoCreatorHabeasCodus`, display name "Demo Creator") and enabled the Email/Password
  provider on the `habeas-codus` project (Google was the only enabled provider before).
- **Copied the creator's content** (`4TMpUIyCU5R6B21Ito9OcCRVebf2`, Ankit Mishra) into the demo
  user: 482 Firestore documents and 16 GCS objects (3 projects, transcripts + segments, analysis
  runs/findings/heatmap bins, caption render, draft, persona, avatar). Connected accounts and
  their encrypted OAuth tokens are deliberately **not** copied.
- **Hard read-only enforcement (backend).** New `READ_ONLY_USER_UIDS` setting (comma list or
  JSON array). A new `ReadOnlyMiddleware` rejects every `POST/PUT/PATCH/DELETE` from a listed UID
  with `403 FORBIDDEN` / `details.reason = "read_only_demo"` *before* any router or service runs.
  It is path-based, not per-route, so future mutating endpoints are covered automatically. The
  only exception is `POST /projects/{id}/thumbnails/download` (reads/zips stored images), which
  is allow-listed.
- **`Me.readOnly`.** `AuthenticatedUser.read_only` is derived from the setting; `/me` returns it
  and the web client uses it. The verified token claims are cached on `request.state` so a write
  is not verified twice.
- **UI disabled with tooltips.** `useReadOnly()` + `READ_ONLY_REASON` +
  `<DisabledReason>` (a Base UI tooltip on an inline-flex span, because a disabled base `Button`
  has `pointer-events-none` and cannot host its own tooltip). Every mutating control is disabled
  and explains why: create/edit/delete project, upload/revision, transcript edit + re-run,
  caption render/delete, run analysis, dub + delete, glossary save, thumbnail generate/revise/
  apply/delete, publish/retry/delete, YouTube connect/sync/disconnect, avatar save, persona/
  onboarding, delete account, draft generate/edit/brief/chat. A persistent `ReadOnlyBanner` sits
  above the app content.
- **Allowed on purpose:** viewing transcript/analysis versions, local exports (transcript SRT/
  VTT, thumbnail ZIP/PNG, caption/dub downloads), feature flags, theme, copy-token, sign out.
- **Demo sign-in.** Landing page shows a one-click "Try the demo" (hero + CTA) when
  `NEXT_PUBLIC_DEMO_EMAIL`/`NEXT_PUBLIC_DEMO_PASSWORD` are set; it signs in with email/password.
- **Copy script** `backend/scripts/copy_user_content.py --source <uid> --dest <uid> [--replace]`
  walks the `users/{source}` subtree, rewrites `ownerUid` and `users/{source}/` storage paths,
  copies objects under the matching prefix, and stamps `readOnly: true` on the dest user doc.

## Structural changes

- Backend: `app/auth/read_only.py` (new), `app/main.py` (middleware, ordered so CORS wraps it),
  `app/dependencies.py` (`read_only` on `AuthenticatedUser`, claim reuse), `app/config.py`
  (`read_only_user_uids`), `app/schemas/users.py` + `app/services/user_service.py`
  (`Me.readOnly`), `backend/scripts/copy_user_content.py` (new).
- Web: `lib/read-only.tsx` + `lib/demo.ts` (new), `components/common/disabled-reason.tsx`,
  `components/layout/read-only-banner.tsx`, `TooltipProvider` in `app/providers.tsx`,
  `Me.readOnly` in `lib/types.ts`, `signInAsDemo`/`demoAvailable` in the auth provider, and
  read-only disabling across ~20 components.
- Contracts/infra: `contracts/openapi.yaml` (`Me.readOnly`), `infra/RESOURCES.md` (demo account +
  Email/Password provider), `backend/.env.example` / `.env.deploy.example` /
  `web/.env.example`. Local `backend/.env` and `web/.env.local` carry the real UID/credentials.

## Decisions / gotchas

- Enforcement is an **env allowlist**, not a Firestore flag, so it cannot be flipped from the
  app. The copy script also writes `readOnly: true` on the user doc for human clarity, but the
  API does not read that field.
- The middleware must be registered **before** `CORSMiddleware` in `create_app` or the 403 skips
  CORS and the browser reports a CORS error instead of the real message.
- The demo password is public on purpose (a shared, pre-seeded, read-only showcase account). It
  is not a secret and must never gate anything real.
- `DisabledReason` only wraps when a reason is present, so normal accounts get no extra DOM.
- The draft editor and transcript editor are write surfaces, so in read-only they render static/
  blocked views rather than disabling dozens of inner controls.
- Caveat: the demo credentials are public, so a signed-in visitor could call Firebase client
  methods (`updatePassword`/`deleteUser`) on the shared account directly. Fine for a hackathon
  showcase; if it matters later, switch the demo sign-in to a backend-minted custom token and/or
  guard the account with a blocking Cloud Function.

## Verification

- `uv run ruff check .` clean; `uv run mypy app` clean (110 files).
- `bunx tsc --noEmit` clean; `bun run lint` (oxlint) clean; `bun run lint:eslint` only the
  pre-existing `<img>` warning; `bun run build` succeeds.
- Live end-to-end with a real demo ID token (throwaway script, deleted): `/me` → 200
  `readOnly: true`; `/projects` → 3 items; project/transcript/assets/revisions/analysis → 200;
  `POST /projects` → 403 `read_only_demo`; thumbnail-download POST → 422 (reaches the route, i.e.
  not blocked). Smoke-checked the middleware directly too (CORS header + requestId present).
- Cleaned up the one stray project the smoke test created under a fake UID.

## Not done / next step

- Not visually click-tested in a browser. Worth eyeballing: the disabled-tooltip hover on a
  disabled `Button` inside a dialog/alert-dialog trigger, the read-only draft static render, and
  the landing "Try the demo" button.
- If the deployed API is used for the demo, set `READ_ONLY_USER_UIDS=demoCreatorHabeasCodus` and
  the `NEXT_PUBLIC_DEMO_*` vars in the deploy config (already staged in `.env.deploy.example`).
- Uncommitted.
