# Progress — 2026-09-25 06:09 UTC — Humation avatars, no card entrances, shorter player

Uncommitted (not requested).

## Humation avatars (replaces the Gmail photo everywhere)

- Packages: `@humation/react`, `@humation/assets-humation-1`, `@humation/core`
  (MIT, local SVG rendering, no API). Deliberately did NOT install the shadcn
  `avatar-builder` block (assumes Radix shadcn primitives; ours are Base UI) —
  the customizer below is hand-built on `@humation/core` instead.
- Contract-first backend: `AvatarState { seed, selections, colors }` schema on
  `Me`, `PUT /api/me/avatar` (full-state replace, owner-scoped), mirrored in
  `contracts/openapi.yaml`. Tests: replace + `GET /me` reflection + 401.
- Web:
  - `lib/avatar.ts`: `randomAvatarState()` (crypto UUID seed),
    `normalizeAvatarState()`, `updateAvatar()`, `useUserAvatar()`,
    `ensureAvatarAssigned()` (module-deduped single PUT).
  - `components/avatar/user-avatar.tsx`: Humation `<Avatar>` (transparent bg)
    in a rounded clip. `avatar-bootstrap.tsx`: assigns + persists a random
    avatar once for users who have none, then refreshes the profile; mounted in
    `(app)/layout.tsx` inside the auth guards.
  - `avatar-customizer.tsx` (profile page, minimal): live 96px preview, one
    picker row per manifest `uiGroups` entry (bottom/body/head/item/glasses,
    previews via `createPartPreview` as data-URL `<img>`), skin/hair/clothes
    swatch rows, Randomize (fresh seed), Save (PUT + profile refresh).
    Selections stored as canonical part IDs, colors as `#RRGGBB`.
  - Header `UserMenu` and anywhere else: Gmail `photoURL`/`AvatarImage` gone;
    gradient ring kept around the Humation avatar.
- Note: the asset set is ~1.8 MB on disk (embedded SVGs, compress well) and
  ships with the shared bundle since the header renders it. Acceptable for now;
  lazy-loading would only help non-authenticated routes.

## Card entrance animation removed

- Dashboard + `/projects`: the staggered fade/rise `motion.div` wrappers are
  gone — cards render immediately on first load. (Sidebar rail/label motion
  untouched.)

## Shorter video preview

- Workspace player (video.js fluid 16:9): container now `mx-auto max-w-3xl`
  (was full `max-w-4xl` width), so height drops ~504px → ~432px. Error and
  loading states match.

## Verification

- Backend: `pytest` 153 passed, `ruff` + `mypy` clean.
- Web: `oxlint` clean, `oxfmt` clean, `eslint` 0 errors (1 pre-existing
  data-URL `<img>` advisory), `bun run build` passes (Turbopack + tsc).

## Gotchas

- Base UI `Select.Value` intentionally untouched this round; avatar preview
  `<img>`s carry a scoped eslint-disable (generated data URLs, nothing to
  optimize) matching the existing poster precedent.
- `normalizeAvatarState` tolerates partial/legacy payloads so old/foreign
  `avatar` docs can never break rendering.
- Pre-existing accounts get their random avatar lazily on next signed-in visit
  (bootstrap), not via migration.

## Next

- Caption `<track>` from transcription; backend-generated `thumbnail` assets;
  per-card delete menus; Audience/Connections/Settings pages.
