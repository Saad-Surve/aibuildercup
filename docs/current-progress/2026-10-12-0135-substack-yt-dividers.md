# 2026-10-12 01:35 — Substack-as-YT fix, settings dedupe, divider sections

Uncommitted (no commit asked). Continues `0110` (Substack upload fix is in this
tree, verified live).

## 1. Substack shown as a YouTube channel — real bug: unfiltered picker

User saw 2 entries when picking a channel on the project video page. Last
session's subtitle theory was wrong. The actual bug: `YouTubeConnections`
(`youtube-connections.tsx`, used as the studio channel picker with `selectable`)
mapped over the **shared, unfiltered** `["connections"]` list — so the Substack
publication (same owner name "Ankit Mishra") rendered as a second "YouTube
channel" row. The DB holds exactly one YouTube connection (re-verified across
all users); the text-platform list already filtered by platform, only this
component didn't.

Fix: filter to `connection.platform === "youtube"` (with a comment naming the
trap). The "N channels" count now counts YouTube only. No backend change.

## 2. Removed duplicate Connections header, kept outer Card (`settings/page.tsx`)

The page had `PageHeader` ("Connectors") plus a `Card` titled "Connections" with
"Bring your published work into the studio. …" — the card header duplicated the
page title. Removed only the `CardHeader` (title + description); the outer `Card`
wrapping all sections and their dividers stays. Onboarding shares
`AccountConnections` and is unaffected (its own surrounding layout untouched).

## 3. Cards → dividers (`account-connections.tsx`)

The YouTube and Writing-platforms bordered card sections (boxed header with
`border-b bg-muted/20` + padded body) are now plain stacked sections separated
by the shared `Separator`, keeping the same headers/descriptions. Coming-soon
placeholder tiles left as-is. No logic change.

## Verification

- Web `oxlint` + `tsc --noEmit` clean. Backend untouched this round (its `ruff` /
  `mypy` standing from `0110`).
- Tree: 5 files (`substack.py` from `0110`, `youtube-connections.tsx`,
  `settings/page.tsx`, `account-connections.tsx`, `crosspost-card.tsx`).
