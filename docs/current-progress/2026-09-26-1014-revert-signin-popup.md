# Progress — 2026-09-26 10:14 UTC — revert Google sign-in to popup

## What broke
The previous note switched `signInWithPopup` → `signInWithRedirect` to avoid the separate
Google window. In this app that dead-ends: the flow shows the "Taking you to your studio…"
loader and then returns to the landing page signed out. The redirect returns to
`habeas-codus.web.app` and hands the result back through the `habeas-codus.firebaseapp.com`
auth handler; in this browser/setup the result never reaches `onAuthStateChanged`, so the user
lands back on the landing page.

## Fix
- `auth-provider.tsx`: restored `signInWithPopup` as the primary path (it worked). Kept
  `signInWithRedirect` only as a fallback when the popup is blocked
  (`auth/popup-blocked` / `auth/operation-not-supported-in-this-environment`).
- Removed the `getRedirectResult` call from the mount effect; it is not needed for the popup
  path and added noise.

## Note for next time
A truly in-page Google button would need Google Identity Services (`google.accounts.id`
renderButton + `signInWithCredential`) rather than Firebase's redirect. Firebase offers popup
or redirect only, and redirect is unreliable here.
