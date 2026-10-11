# 2026-10-12 01:10 — Substack upload fixed, connected-only destinations, crosspost modal

Three asks: fix Substack upload, only offer connected media as draft destinations,
and move the inline upload section into a modal. Uncommitted (no commit asked).

## 1. Substack upload: missing `draft_bylines` (found live, fixed, verified)

Symptom reproduced through the production path (`CrosspostService.post`):
`POST {pub}/api/v1/drafts` → **400 `{"errors":[{"location":"body",
"param":"draft_bylines","msg":"Invalid value"}]}`**. Substack's internal drafts
endpoint now requires an author byline.

Fix (`backend/app/providers/substack.py`, +11 lines): `create_draft` resolves the
session's own profile id via `get_profile` and sends
`draft_bylines: [{"id": <profile id>}]`. No contract change (provider-internal).

Verified live twice against the user's publication (`2102ankit`): draft created
200 with dashboard URL, then deleted the test draft (`DELETE …/drafts/{id}` 200)
both times. Second run went through `CrosspostService.post` with the final code.

## 2. Only connected media as destinations (`crosspost-card.tsx`)

The platform pills always showed Medium/Substack/Reddit regardless of connections.
Now: pills render only for platforms with ≥1 `connected` connection (derived
during render, so a disconnect narrows choices immediately, no effect needed);
the account dropdown lists only connected accounts; the effective platform /
connection fall back safely (stale ids can never be submitted — the mutation
guards). Loading state ("Loading your connected accounts…") avoids flashing all
platforms; empty state links to `/settings` ("Connect one in Settings"). Trigger
button no longer enumerates platforms ("Post this draft").

## 3. Crosspost form is now a modal (`crosspost-card.tsx`)

The opened `Card` rendered inline in the draft workspace (layout shift). It is now
a `Dialog` (same pattern as `ScheduleDialog`: `DialogContent
max-h-[92vh] overflow-y-auto sm:max-w-lg`, `DialogFooter` with `DialogClose` +
Post). All form logic, prefill, and result link unchanged; closing clears only
the error, draft edits persist while the project page is mounted.

## Verification

- Backend `ruff` + `mypy` (139 files) clean; web `oxlint` + `tsc --noEmit` clean.
- Did NOT run `bun run format`: it reflowed 34 unrelated files (repo is not
  oxfmt-clean) — reverted the churn, re-applied the card edits minimally.
- Final tree: 2 files (`substack.py`, `crosspost-card.tsx`), +123/−63.

## Ops: backend reloader stalls — now running without `--reload`

The `--reload` watcher stalled again on the `substack.py` save ("Reloading…" with
no startup after 15s+; healthz kept serving old code). Killed the tree and
restarted as plain `uv run uvicorn app.main:app --port 8080` (startup complete,
healthz 200, current code incl. the bylines fix). Consequence: backend edits no
longer hot-load — restart the process after backend changes (or ask me to).
Same root cause as the 00:25 note; likely WatchFiles vs OneDrive. If the user
runs their own backend in a terminal, this background one double-binds the port
on their next start — tell them to kill mine or use it.
