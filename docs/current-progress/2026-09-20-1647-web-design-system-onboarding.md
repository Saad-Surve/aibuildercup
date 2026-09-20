# Progress — 2026-09-20 16:47 IST

Status: **design system established, onboarding flow built and wired end to end. A storage
path bug found during live use is fixed.**

## 1. What I did

### Design system

- Ran `shadcn init` (this shadcn is v4 / Base UI, style `base-nova`, not Radix).
- Installed primitives: button, input, textarea, label, field, card, badge, separator,
  progress, select, radio-group, checkbox, sonner, avatar, dropdown-menu, skeleton, tooltip,
  alert, spinner, empty. Added `next-themes`.
- Rewrote `web/src/app/globals.css` with the token system (see `web/DESIGN.md`).
- **Thesis: colour is meaning.** Monochrome chrome + one desaturated "signal" blue for
  interactive affordances; the severity/heatmap scale is the only other colour. Geist for UI,
  Geist Mono (`.tabular`) for timestamps/scores/IDs. One radius scale (10px controls / 14px
  surfaces). Light + dark, driven by `next-themes`.
- `web/DESIGN.md` documents tokens, conventions, and the **full future component inventory**
  derived from `frontend-plan.md` §4–§14, with status.

### Onboarding + shell

| File | What |
|---|---|
| `web/src/lib/onboarding.ts` | Step metadata, option lists, per-step answer slicing |
| `web/src/components/onboarding/steps.tsx` | Welcome, Identity, Topics, Audience, Style, Platforms, Persona, Done |
| `web/src/components/onboarding/onboarding-flow.tsx` | Orchestrator: load progress, PUT per step, complete, persona edit |
| `web/src/components/onboarding/step-rail.tsx` | Numbered rail (a real sequence, so numbering is information) |
| `web/src/components/common/{logo,centered-screen,page-header,chip-select}.tsx` | Shared primitives |
| `web/src/components/auth/guards.tsx` | `RequireAuth`, `RequireOnboarded` |
| `web/src/components/layout/{app-shell,user-menu}.tsx` | Sidebar + topbar + user menu with theme control |
| `web/src/app/(onboarding)/...` | Focused onboarding route (no app chrome) |
| `web/src/app/(app)/dashboard/page.tsx` | Minimal dashboard placeholder (empty state) |
| `web/src/app/(app)/layout.tsx` | `RequireAuth` → `RequireOnboarded` → `AppShell` |
| `web/src/components/auth/auth-provider.tsx` | Added `refreshProfile()` |
| `web/src/components/auth/login-page.tsx` | Signed-in users now redirect by onboarding status |

Flow: login → `/me` → if `onboardingCompleted` `/dashboard` else `/onboarding`. Onboarding
persists each step with `PUT /onboarding`, calls `POST /onboarding/complete` on leaving the
platforms step, fetches `GET /persona`, allows edits via `PATCH /persona` (version-checked),
then `/dashboard`.

## 2. Bug found and fixed (backend)

Live use of the persona step failed with a 500. Cause: `validate_object_path` reused the
Firestore id rule (`^[A-Za-z0-9_-]+$`), which rejects dots, so the persona object path
`users/{uid}/profile/persona.md` was rejected as an "invalid path segment". Fixed
`storage_service.validate_object_path` to validate only what matters for GCS: relative, no
backslashes, and no empty / `.` / `..` segment. Dots in filenames are now allowed. Added
`tests/test_storage_paths.py`. Backend restarted.

## 3. Decisions / gotchas

- This shadcn generation is **Base UI**, not Radix, and components are composed differently
  (e.g. `DropdownMenuTrigger render={<Button/>}`, `Select onValueChange`). Follow the examples
  in the installed `ui/*` files, not older shadcn docs.
- `next-themes` is required by the generated `sonner.tsx`. It also gives us the `.dark` class
  and system preference, so no custom theme script.
- The onboarding page lives outside `(app)` so it isn't wrapped in the sidebar shell.
- `ChipSelect` is used for multi/single choices instead of radio groups — lighter visually and
  consistent across steps. Radio-group is available if a step later needs it.
- The dashboard is intentionally a placeholder; it exists so the post-onboarding redirect has
  a destination and to exercise the shell.

## 4. Verification

- `bun run lint` clean; `bun run build` clean (routes `/`, `/login`, `/onboarding`,
  `/dashboard`).
- `bun run` backend: `pytest` 58 passed, `ruff` clean, `mypy` clean.
- Live backend log showed the real browser hitting `GET /me`, `GET /onboarding`,
  `PUT /onboarding` → 200. That is what surfaced the storage bug.
- After the fix the API was restarted; the persona step should now succeed.

## 5. Not done / next step

- **Verify the persona step end to end after the storage fix** (generate, edit, save, reach
  the dashboard). This was the step that failed before the fix.
- Email/password sign-in is still disabled in Firebase; `EmailSignInForm` is deferred.
- Next build is the dashboard/project list + upload flow, then the transcript + heatmap
  workspace. The component inventory in `web/DESIGN.md` is the checklist.
- A manual theme toggle exists in the user menu; both modes should still get a visual pass.
