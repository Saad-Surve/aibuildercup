# 2026-10-11 23:26 — Substack connect: research + frictionless cookie flow

## The research (why this is the best possible)

The ask was "fetch the latest Substack connector and connect without pasting
cookies." I checked what Substack actually offers (live probes):

- **No official write API.** Draft/publish still go through the same internal,
  cookie-authenticated endpoints the editor uses (`POST …/api/v1/drafts`).
- **There *is* an official OAuth server** —
  `https://substack.com/.well-known/oauth-authorization-server` (issuer
  substack.com, endpoints `/oauth/auth`, `mcp.substack.com/oauth/token`, dynamic
  registration at `mcp.substack.com/oauth/register`). **But** every dynamic
  registration — regardless of requested scope — is granted only
  `mcp:read offline_access`. It is Substack's MCP auth and is read-only; the
  advertised `notes.write` / `design-data` scopes are not actually issued to
  public clients. So OAuth cannot create drafts or posts.
- **Password login is captcha-gated.** `POST substack.com/api/v1/login` returns
  `Please complete the captcha to continue`, so a server-side email/password
  login is not viable either.
- Community MCPs/libraries (`ma2za/python-substack`, `submarckts`, etc.) all use
  the session cookie for anything that writes.

**Conclusion:** the `substack.sid` session cookie is the only way to post.
There is no honest cookie-free path. So the fix is to remove every *other* piece
of friction and accept any paste.

## What I changed

**Backend**
- `providers/substack.py`: new `extract_sid` accepts a bare `substack.sid`
  value, a `substack.sid=…; …` pair, or the whole cookie header (devtools
  "Copy"), and errors clearly (`SUBSTACK_BAD_COOKIE`) otherwise; new
  `list_publications`; `pick_publication` now reuses it.
- `schemas/connections.py`: `SubstackConnectRequest.subdomain` is optional;
  `sid` accepts the full header (length raised).
- `services/connection_service.py`: `connect_substack` auto-detects the
  publication — one publication connects straight away, several raise
  `SUBSTACK_MULTIPLE_PUBLICATIONS` with `details.publications` so the UI can
  offer a picker. The stored cookie is the extracted sid.
- `contracts/openapi.yaml`: `SubstackConnectRequest` — `subdomain` optional.

**Web**
- `api-client.ts`: `ApiError` now carries `details` (so the UI can read the
  publication list).
- `lib/connections.ts`: `connectSubstack(sid, subdomain?)`.
- `accounts/text-platform-connections.tsx`: single cookie field (no required
  subdomain); on `SUBSTACK_MULTIPLE_PUBLICATIONS` it renders a publication
  picker; the optional subdomain field only shows as a fallback; copy/hint
  updated.

**Docs:** `docs/connectors/text-platforms-setup.md` Substack section rewritten
(one pasted cookie, auto-detected publication, the OAuth/captcha findings).

## Verification

- `extract_sid` unit-checked across bare / pair / quoted / whole-header / wrong
  forms.
- `ruff` + `mypy` (139 files) clean; `oxlint` + `tsc` clean.
- Not exercised against a live Substack account (needs a real session cookie).

## Not done / next

- If Substack ever issues write scopes on its OAuth server, swapping the cookie
  for an OAuth token is a one-provider change.
- A one-click bookmarklet that copies `substack.sid` could shave the last paste;
  deferred (cross-origin `javascript:` link quirks).
