# Draft variant underline spans the whole group

## What I did

The dashed underline that marks a versioned draft section was drawn by an absolutely-positioned
`::after` border on `.draft-variant`. A border on an inline box draws once at the bottom of the
box, so a group that wrapped across several lines showed a single underline under the **last
line only**.

Replaced it with real `text-decoration` on the variant:

```css
text-decoration-line: underline;
text-decoration-style: dashed;
text-decoration-color: var(--alt-color);
text-decoration-thickness: 1.5px;
text-underline-offset: 3px;
```

`text-decoration` underlines every line the group covers, so the whole edited section reads as
underlined, and it still follows `--alt-color` (muted for the original, `--signal` for a changed
version). Removed the now-redundant `.draft-variant::after` and `.draft-variant-heading::after`
rules. Web-only (`web/src/app/globals.css`).

## Verification

- `next build` succeeds; `tsc`/`oxlint`/`eslint` unaffected.

## Not done / next step

- Committed and pushed.
