# Connecting Medium, Substack, and Reddit — detailed setup

All three live in the app under **Settings → Writing platforms** (and the same
cards appear during onboarding). What each one needs, step by step, is below.
Honest limits first: only Reddit has a healthy official OAuth. Medium's API is
deprecated and Substack's is unofficial — both still work, with the caveats
spelled out per platform.

## Medium — legacy integration token only

**The one thing to know:** Medium deprecated its API and stopped issuing new
integration tokens in January 2025. If you never generated one, you cannot
connect Medium — no workaround exists (Medium also left Zapier over this).
If you hold a pre-2025 token, it still authenticates and posts.

1. Go to [medium.com/me/settings](https://medium.com/me/settings) → **Security**
   → **Integration tokens**. If the section is gone, your account has no token
   and Medium will not give you one.
2. Copy the token (a long hex string). Treat it like a password.
3. In the studio: **Settings → Writing platforms → Medium → Connect Medium**,
   paste the token, Connect.
4. The card shows your Medium name; Disconnect removes the stored token (Medium
   offers no server-side revoke).

Posting: title + Markdown body, visibility **Draft** (default, only you),
**Unlisted**, or **Public**. Drafts land in your Medium drafts; public posts go
straight to your profile. Optional: `canonicalUrl` if the piece first lived
elsewhere (avoids duplicate-content penalties), up to 3 tags.

## Substack — publication subdomain + session cookie

**The one thing to know:** Substack has no official write API. The connector
drives the same cookie-authenticated endpoints the Substack editor uses, so it
works (draft → publish → schedule, email sends included) but is inherently
fragile: the cookie expires and internal endpoints can move. When posting
starts failing, reconnect with a fresh cookie.

1. You need a publication (e.g. `yourname.substack.com`) where you can post.
2. In Chrome/Edge, log into Substack, then open devtools (**F12**) →
   **Application** → **Cookies** → `https://substack.com` → copy the value of
   the `substack.sid` cookie (very long string).
3. In the studio: **Settings → Writing platforms → Substack → Connect
   Substack**, enter the subdomain (`yourname` — bare name, full domain, or URL
   all work) and paste the cookie, Connect.
4. The card shows your publication name; Disconnect deletes the cookie.

Posting: title, Markdown body (headings/bold/italic/links convert; anything
fancier posts as plain text), optional subtitle. Modes: **Draft** (default,
review in Substack first — recommended), **Publish now** (choose whether to
email subscribers; sending is irreversible), **Schedule** (UTC time). Audience
defaults to everyone; subscribers-only and paid options exist.

## Reddit — official OAuth (the smooth one)

Free tier: 100 calls/minute per app, personal/non-commercial use. Our posting
uses a handful of calls per post, so you will never feel the limit. Commercial
use needs a Reddit contract — out of scope for the demo.

**First, create the Reddit app (one-time, ~3 minutes):**

1. Log into Reddit → go to [reddit.com/prefs/apps](https://www.reddit.com/prefs/apps)
   → **Create app** (or "Create another app").
2. Name it anything (e.g. `Creator Studio`), choose type **web app**.
3. Redirect URI must be exactly:
   - local dev: `http://localhost:8080/api/connections/reddit/oauth/callback`
   - deployed: `https://<your-api>/api/connections/reddit/oauth/callback`
   (or set `REDDIT_OAUTH_REDIRECT_URI` and register that exact value instead).
4. Create. Note the **client ID** (under the app name, ~14 chars) and the
   **secret** (in the app details).
5. Put them in `backend/.env` as `REDDIT_OAUTH_CLIENT_ID` /
   `REDDIT_OAUTH_CLIENT_SECRET` (local), or into Secret Manager with the same
   names (deployed), then restart/start the backend.
6. In the studio: **Settings → Writing platforms → Reddit → Connect with
   Reddit**, approve `identity + submit + read`. You land back in Settings with
   `u/you` connected.

Caveats, learned the hard way:

- Since late 2025 Reddit sometimes funnels new apps through a manual Developer
  Support pre-approval instead of instant activation. If your client ID/secret
  returns errors on first use, file the approval form (linked from the Reddit
  help center's Data API wiki) and wait — there is no code fix for this.
- Posting to **your own profile** (the default — blank subreddit posts to
  `u/you`) always works. Subreddits are individual kingdoms: many block bots,
  require karma, or demand flair — a removal there is moderation, not a bug.
- Refresh tokens are permanent (`duration=permanent`); the hourly access token
  refreshes silently. There is no server-side revoke, so Disconnect just deletes
  the tokens (also remove the app at `prefs/apps` if you want it fully gone).

Posting: title + text (or a link URL for link posts), optional subreddit,
send-replies toggle, nsfw/spoiler flags. Live URL comes straight back.

## Posting from a draft

Open any written draft → **Post to Medium / Substack / Reddit** (under the
header). Pick the platform, pick the connected account, adjust title/body —
both prefill from the draft — choose the safe default or go public, Post. The
result line links straight to the live post or draft.
