# 2026-10-12-0128 — Platform logos everywhere, dropdown labels, unicode arrows

## What I did
- **Platform logos alongside every platform name:**
  - `ChipSelect` now supports an optional per-option `logoSrc` (rendered with
    `next/image`); onboarding `PlatformsStep` and `CreateProjectDialog` pass
    `platformLogoSrc(value)` for each platform chip, so YouTube/Instagram/
    TikTok/X/Facebook/LinkedIn/Shorts chips all show their SVG logo.
  - Schedule dialog platform dropdown: the selected display now renders
    `PlatformLogo + platformLabel` inside `SelectValue` (was label-only text);
    removed the duplicate standalone logo outside the trigger.
  - Library detail badges: `{selected.platform}` (raw value like `youtube`)
    now renders `PlatformLogo + platformLabel`; language badge uses
    `languageLabel` instead of the hardcoded hi/en special-case.
  - Landing calendar demo card: platform name now has its logo inline next to
    the label (was text-only at the top, logo only at the bottom).
  - Connections/settings pages already paired logo + name — no change.
- **Dropdown selected display shows the label, not the underlying value:**
  - `platformLabel` is now case-insensitive and covers out-of-list values
    (`youtube_shorts` -> "YouTube Shorts", `twitter` -> "X"); `platformLogoSrc`
    maps `youtube_shorts` to the YouTube SVG. Calendar/platform and onboarding
    vocabularies disagree (`youtube_shorts` vs `medium/substack/reddit`), so
    stored values from one surface no longer render raw on the other.
  - Transcript editor header and library map-pin tooltips: raw language codes
    now go through `languageLabel`.
  - Verified all other `SelectValue` usages: bare ones render `ItemText`
    (the label) by Base UI design; custom render fns all map value -> label
    (project name, connection display name, `v${n}` versions) — no raw-value
    leaks left.
- **Actual arrows instead of unicode arrows:** replaced every `→` (U+2192) in
  `web/src` comments with ASCII `->`. Rendered UI already uses real icons
  (`InlineArrow` / Hugeicons `ArrowRight01Icon`, etc.) — no UI text used a
  unicode arrow. Verified zero unicode arrows remain in `web/src`.
- Added a `PlatformBadge` (logo + label) export in
  `components/calendar/platform.tsx` for future platform displays.

## Structural changes
- `components/calendar/platform.tsx`: `platformLabel`/`platformLogoSrc`
  hardened (case-insensitive, alias map), new `PlatformBadge` export. Contract
  unchanged (no API/firestore change).
- `components/common/chip-select.tsx`: `ChipOption.logoSrc?` added; chips
  render logo + label with `gap-1.5`.
- No backend/infra changes.

## Decisions / gotchas
- Did NOT add `youtube_shorts` as a selectable calendar option (would change
  product behavior); only the label/logo resolvers know about it.
- Base UI `Select.Value` with no children renders the selected item's text
  (label), not the value — so bare `<SelectValue />` usages were already
  correct and were left alone.
- `languageLabel(undefined)` returns "Select language"; only called with real
  codes in the touched spots.

## Verification
- `bun run lint` (oxlint): clean.
- `bun run build` (Next.js 16.3.5 Turbopack): compiled + static export OK.

## Not done / next step
- `selected.contentType` / `kind` badges on the library page still show raw
  values — out of scope for this request, could get the same label treatment.
- Calendar upcoming/day rows show logo-only (no platform text) for space;
  they have no tooltip — could add `title={platformLabel(...)}` later.
