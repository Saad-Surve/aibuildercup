# Fix "Unknown draft block" on save

## What I did

Removed the block-id validation in `DraftService.save`. The web client owns block creation
(splitting a paragraph, merging, a fresh block), so the save payload is the full block set —
a replace, not a patch — and can legitimately contain ids the server has not seen yet. The
validation treated those as an error and every edit after a split failed with
`400 Unknown draft block`.

`PUT /draft` now accepts the payload's blocks as-is. The OpenAPI description was updated to
say the body is a replace.

## Verification

- Backend: `ruff` clean, `mypy` clean (79 files).
- Web: `tsc` clean, `oxlint` clean, `next build` succeeds.

## Not done / next step

- Everything from the last four rounds is being committed and pushed now.
