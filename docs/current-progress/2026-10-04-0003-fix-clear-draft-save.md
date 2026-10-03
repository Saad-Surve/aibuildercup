# Fix: clearing the draft was ignored by the server (chat restored deleted content)

## What I did

Fixed the footgun where deleting content and then asking the writing partner for an opening line
brought the deleted content back.

**Root cause (backend).** `DraftService.save` guarded the block replace with `if payload.blocks:`.
An empty list — the client's way of saying "I deleted everything" — is falsy, so the server kept the
old blocks. The subsequent `assist` call then read the stale full draft, so the model "restored"
everything and appended the opening line below it.

**Fix.** Replace the truthiness check with a presence check:

```python
if "blocks" in payload.model_fields_set:
    draft.blocks = payload.blocks
```

The client always sends `blocks`, so an explicit `[]` now clears the draft; an omitted field still
leaves the blocks untouched. The OpenAPI contract is unchanged (`blocks` stays a plain array).

## Files

- `backend/app/services/draft_service.py`

## Verification

- `uv run ruff check .` clean; `uv run mypy app` clean (97 files).
- Confirmed the Pydantic presence semantics with a one-off script:
  `SaveDraftRequest(title=…)` → `model_fields_set == {'title'}` (untouched);
  `SaveDraftRequest(title=…, blocks=[])` → `{'title', 'blocks'}` (clears).
- Web unchanged this round but re-verified: `tsc` clean, `oxlint` clean, `eslint` 0 errors
  (1 pre-existing `<img>` warning), `next build` succeeds.

## Not done / next step

- The frontend could also refuse to run `assist` if `flushSave` fails (it currently rejects the
  promise); not needed for this bug.
- Committed and pushed this session.
