# Draft chat: keep bubbles out of the avatar gutters

## What I did

The assistant bubble was `max-w-[88%]`, which on a typical chat column reached past the
x-position of the user avatar on the right. Tightened both bubble widths so each stays inside the
central column and never overlaps an avatar gutter:

- user → `max-w-[75%]`
- assistant → `max-w-[78%]` (was 88%)

## Files

- `web/src/components/projects/draft/draft-chat.tsx`

## Verification

- `tsc` clean, `oxlint` clean, `next build` succeeds.
- Backend untouched.

## Not done / next step

- Not click-tested; the two widths are the knob if either side wants to be wider.
- Uncommitted.
