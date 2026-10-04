# Fix: "page couldn't load" was Base UI error 31 (Menu group context)

## Root cause

The user's "this page couldn't load" was the Base UI production error
`https://base-ui.com/production-error?code=31`, i.e.:

> Base UI: MenuGroupContext is missing. Menu group parts must be used within `<Menu.Group>` or
> `<Menu.RadioGroup>`.

The seed channel dropdown (`youtube-connections.tsx`) put `DropdownMenuLabel` and the
`DropdownMenuItem`s directly in `DropdownMenuContent`, without a `DropdownMenuGroup`. In
production, Base UI throws on render, which the browser surfaced as a generic page error. (Dev
builds show the full message; production shows the code.)

## Fix

Wrapped the label, separator, and items in `<DropdownMenuGroup>` (matching the existing
`user-menu.tsx` pattern).

## Verification

- `bunx tsc --noEmit`, `bun run lint`, `bun run build` clean (production build — where the code
  would have thrown).

## Notes

- The seed endpoint itself always worked (`POST /api/seed/youtube-content` → 200). The crash was
  purely the dropdown rendering.
- Lesson: every Base UI group part (`Menu.GroupLabel`, and group items) must sit inside
  `Menu.Group`/`Menu.RadioGroup`; the dev build warns, the production build throws a coded error.

## Not done / next step

- Confirm the seed dropdown renders on the deployed site.
