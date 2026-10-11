# 2026-10-12 02:40 — Substack two-way link, modal without Body, Ctrl+S saves

Uncommitted. Answers "is there no 2-way link?": there wasn't — posting was
one-shot. Now posting a Substack draft/schedule records the remote draft on the
local draft, and Sync pushes later edits into it.

## Backend

- `providers/substack.py`: new `update_draft` (PUT `…/drafts/{id}` with TipTap
  body + byline). 404 maps to `SUBSTACK_DRAFT_GONE`. Verified live: created a
  draft, updated it (read-back confirmed new text), deleted it, then confirmed
  updating the deleted id raises the gone error.
- `schemas/draft.py`: `LinkedExternalPost {platform, connectionId, externalId,
  url, status, updatedAt}` + `Draft.linkedPosts[]` (one per platform).
- `schemas/connections.py`: `SyncCrosspostRequest {platform, title, body}`;
  fixed the stale "Substack converts to HTML" docstring (TipTap now).
- `draft_service.py`: `record_external_post` / `clear_external_post` — targeted
  `update_document` writes, no content/status side effects; failures only log so
  a succeeded post never reports failure.
- `crosspost_service.py`: `post()` records the link for Substack draft/schedule
  results; new `sync()` — 409 when unlinked (post first), 400 for non-Substack,
  reconnect 409s, clears the link when the connection is gone or the remote
  draft was deleted (409 "post again"). Constructor gains `drafts` (wired in
  dependencies; import-cycle checked).
- `api/crossposts.py`: `POST /projects/{id}/crossposts/sync` → 200
  `CrosspostResult`. Route proven mounted on the live server (401 without token,
  not 404).
- Contracts: openapi 82 paths + `SyncCrosspostRequest`/`LinkedExternalPost`/
  `Draft.linkedPosts`; firestore.md draft section documents the link lifecycle.

## Web

- Modal (`crosspost-card.tsx`): Body textarea removed — the editor pane is the
  body (a note under Title says so); post/sync always use the live draft cache
  at submit time. Linked Substack state shows "Linked to your Substack draft —
  Open draft" with the primary button flipping to **Sync changes** (stays a
  normal Post flow when picking publish/schedule or unlinked platforms).
  Post/sync success invalidates `["draft"]` so the linked state arrives; a
  gone-remote refetch falls back to post-fresh.
- `types.ts`: `LinkedExternalPost`, `Draft.linkedPosts`, `SyncCrosspostInput`;
  `connections.ts`: `syncCrosspost()`.
- Ctrl+S / Ctrl+Shift+S (`draft-workspace.tsx`): keydown effect calls the
  existing `flushSave` (debounce flush + server persist) with a "Draft saved"
  toast; `preventDefault` stops the browser save-page dialog. Scoped to the
  workspace mount; read-only mode untouched. Failure surfaces once via the save
  mutation's own error toast.

## Verification

- `ruff` + `mypy` (139 files) clean; `oxlint` + `tsc` clean.
- Live Substack loop end-to-end: post → link on draft doc → edit → sync →
  read-back showed the edited text on Substack → test draft deleted → stale link
  cleared. Backend restarted (no `--reload`) on the final code; healthz 200.
