# Progress — 2026-09-26 10:09 UTC — full-width workspace, redirect sign-in, muted placeholders

## Workspace width
- `project-workspace.tsx`: the workspace container (and its loading skeleton) dropped
  `mx-auto max-w-7xl` for `w-full`, so the 2-pane layout uses the available width on large
  screens instead of centering inside 80rem of side padding. `AppShell`'s `md:px-8` is the only
  inset left. The "project not found" state keeps `max-w-4xl`.

## Google sign-in
- `auth-provider.tsx`: `signInWithPopup` → `signInWithRedirect`, so the OAuth flow runs in the
  current tab/page rather than spawning a separate Google window. Added `getRedirectResult` on
  mount to complete the round trip and surface any error.

## Placeholders
- `Input`, `Textarea`, `Select` placeholders moved from `text-muted-foreground` to
  `text-muted-foreground/60` (including the Select's `data-placeholder`), so hints read as
  hints.

## Back to profile
- Added `ArrowLeft01Icon` to the "Back to profile" button in the onboarding header and in the
  edit-mode finish step.

## Verified
- Web: `tsc --noEmit` clean, `oxlint` clean, `next build` passes.
