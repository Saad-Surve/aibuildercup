# Official brand SVGs everywhere + link icons instead of arrow chars

## Brand icons (web only)

HugeIcons brand glyphs are gone from the app. The official SVGs already in
`web/public/` (`youtube.svg`, `instagram.svg`, `tiktok-mono.svg`, `x.svg`,
`facebook.svg`, `linkedin.svg`) are now the single source through the existing
`PlatformLogo` (`components/calendar/platform.tsx`, next/image based):

- `account-connections.tsx` (the screenshot): YouTube section header
  (`YoutubeIcon text-signal` → official logo), Instagram/Facebook/LinkedIn tiles
  (brand HugeIcons → `PlatformLogo`), X tile (the `𝕏` text char → official `x.svg`).
  Brand imports removed.
- `youtube-connections.tsx`: channel-count row and avatar-fallback both
  `YoutubeIcon` → `PlatformLogo platform="youtube"`.
- Verified: repo-wide grep for brand HugeIcons (`outubeIcon`, `nstagramIcon`,
  `acebook0`, `inkedin0`, `iktokIcon`, `witterIcon`, `oogle*Icon`) returns nothing.
  Landing page already used the official SVGs; untouched.

## Arrow chars in links (web only)

Convention: internal nav links get `ArrowRight01Icon`, external new-tab links get
`ArrowUpRight01Icon` (both verified present in core-free-icons), inline
`size-3`/`size-3.5` with `inline-flex items-center gap-1` on the anchor:

- `account-connections.tsx`: `creator library ↗` → text + `ArrowRight01Icon`.
- `settings/page.tsx`: `Open your library →` → text + `ArrowRight01Icon`.
- `library/page.tsx`: `Open original ↗` (external `target=_blank`) → text +
  `ArrowUpRight01Icon`.

Left alone deliberately (not links, per the request's scope): instructional
`Settings → Connections` breadcrumb in `data-deletion`, `Profile → Connected
channels` helper in `draft-context-panel`, landing `EN → HI` demo metadata, and
code comments.

## Verification

- `bun run lint` clean; `bun run lint:eslint` 0 errors (only the 4 pre-existing
  `<img>` warnings); `bun run build` clean, all routes prerender. No `format` run,
  so no oxfmt churn (`git status` shows only the 5 intended file touches).
- Backend untouched.

## Not done / next step

- Visual check of the connections/settings/library pages in dev (logo sizing in the
  muted tiles, icon alignment in links).
