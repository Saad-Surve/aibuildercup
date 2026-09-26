# Progress — 2026-09-26 09:59 UTC — sidebar first-paint, avatar zoom

## Sidebar hard-refresh flash (real fix)
The pre-paint script + `!important` width override did not help because `AppShell` is **not**
in the prerendered HTML at all — `RequireAuth`/`RequireOnboarded` render a loader until Firebase
auth resolves, so the rail only mounts on the client. The old `useSyncExternalStore` hook seeded
the state to `false` (expanded) and only corrected it in an effect, so the first client render
was always expanded.

- Replaced the store with `useState(readStoredCollapsed)`. Because the rail is client-only there
  is no server snapshot to match, so reading localStorage in the lazy initializer gives the
  correct state on the very first render — no expanded-then-collapse animation.
- Removed the now-unneeded inline script in the root layout and the
  `html[data-sidebar="collapsed"]` CSS override.

## Avatar
- The Humation manifest has a single crop with a lot of empty margin around the head, so the
  face was tiny. Instead of growing the whole component (previous attempt), the SVG is now
  zoomed **1.4×** inside the clipped circle with `transform-origin: 50% 42%` (anchored on the
  face). Verified by rendering the avatar with sharp at several zoom levels; 1.4 keeps the head
  fully framed.
- Reverted the component sizes: header 38px (button h-11), profile editor preview 96px,
  customizer preview 128px.

## Already fixed
- Review-pane snap skip (confirmed by the user).

## Verified
- Web: `tsc --noEmit` clean, `oxlint` clean, `next build` passes.
