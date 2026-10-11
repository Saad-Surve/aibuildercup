# 2026-10-12 02:05 — Substack bodies stored as TipTap, not HTML

User report: posting a draft to Substack pasted literal `<p>…</p>` tags into the
post. Uncommitted.

## Root cause (proven against a hand-written draft)

`GET …/api/v1/drafts/166535307` (the user's own "How to use the Substack
editor" draft) shows `draft_body` is a **TipTap JSON document**
(`{"type":"doc","content":[{"type":"paragraph",…}]}`), not HTML. Substack's
editor stores the body verbatim and renders it as TipTap — our HTML string was
kept as literal text, tags and all. Creation returned 200 either way, so the
old code "worked" while producing broken posts.

## Fix (`backend/app/providers/substack.py`)

- Replaced `markdown_to_substack_html` with `markdown_to_substack_doc`: headings
  (levels 1–3), paragraphs with `hardBreak` line breaks, `**bold**`,
  `*italic*`, `[text](url)` (link mark with href+target), and `>` blockquotes —
  all as TipTap nodes. Anything fancier stays literal text. No HTML is emitted
  at all (verified: converter output contains no tags).
- `create_draft` sends the doc string as `draft_body`. No contract change
  (provider-internal). Fixed two self-review defects before verifying: the `em`
  mark was dropped on nested italic content, and a mypy `no-redef`.
- `ruff` + `mypy` (139 files) clean.

## Verified live (then cleaned up)

Posted "Render check - safe to delete" through `CrosspostService.post`, read it
back: stored `draft_body` parses as `{"type":"doc"}` with heading + paragraph
nodes — structurally identical to hand-written drafts, so it renders formatted.
Deleted the test draft (`DELETE … 200`).

## Ops

The no-reload backend predated this fix, so restarted it (kill 16504, fresh
`uv run uvicorn app.main:app --port 8080`, startup complete, healthz 200).
Reminder standing: backend edits need a manual restart; no `--reload` (it
stalls on this machine).
