/**
 * Public read-only demo account.
 *
 * The demo is passwordless: the landing page asks the API for a short-lived Firebase custom
 * token (`POST /demo/session`) and signs in with it. The account is read-only server-side (see
 * `READ_ONLY_USER_UIDS`), so the shared session can only ever browse.
 */
export const DEMO_ENABLED = process.env.NEXT_PUBLIC_DEMO_ENABLED === "true";
