# 2026-10-11 — Session changelog (web fixes, git surgery, landing calendar)

Consolidated record of one working session. It merges these notes, all now
deleted: `2026-10-11-1615-stash-integration`, `-2029-dev-server-css-fix`,
`-2034-remove-stash-integration-and-push`, `-2043-header-and-project-card-polish`,
`-2051-landing-calendar-animation`, `-2059-sidebar-icon-and-calendar-refinements`.

---

## 1. Dev server "CssSyntaxError" was a stale `.next`, not CSS (20:29)

Next.js 16.3.5 / Turbopack was crashing on `src/app/globals.css` with a
`package.json (directory description file): SyntaxError`. The file on disk was
valid JSON (`node -e JSON.parse(...)` → OK). The dev server had evaluated
`web/package.json` **mid-write** (its mtime was newer than the running `.next`
cache) and cached the bad read.

Fix: kill the stale `next dev` processes, `rm -rf web/.next`, restart. Verified
`GET /` 200 and a 197 KB compiled Tailwind chunk. Dev logs now go to `%TEMP%`,
not the repo. **This is the recurring signature: a stale `.next` from a
mid-edit restart — not a CSS bug.**

## 2. Removed commit `41d854c`, rebased on remote, pushed (20:34)

- Backed the commit up to `backup/stash-integration-41d854c`, then
  `git reset --hard 7f4fde7` to drop it entirely.
- `git fetch` showed the remote had advanced 5 commits (`50e4d40..97d70d6`:
  packaging, Veo grounded inserts, reviewer-heatmap fixes, README/docs). Local
  had diverged, so rebased the one local commit onto `origin/main` — clean
  auto-merge, no conflicts. Validated `contracts/openapi.yaml` (81 paths).
- Pushed fast-forward, **no force**: `97d70d6..4618f58 main -> main`.
- The `2026-10-11-1615-stash-integration.md` note documented that removed
  commit; its content is folded into this file.

**Gotcha:** a rejected push means `fetch` + rebase, never force — a force here
would have destroyed 5 teammate commits.

## 3. Header + project-card polish (20:43)

- `projects/project-card.tsx`: **corner-gap fix** — `Card` renders `rounded-lg`
  but the thumbnail wrapper was `rounded-t-xl` (larger), so the fill curved in
  more than the card ring and the background showed as a crescent. Changed the
  wrapper to `rounded-t-lg`.
- `layout/user-menu.tsx`: avatar button `h-11 w-11` → `h-9 w-9`, `UserAvatar
  size={38}` → `size={30}` (whole widget 42 px → 34 px).
- `layout/app-shell.tsx`: header right cluster `gap-1` → `gap-2` (4 px → 8 px
  between the notification button and the avatar).

## 4. Landing demo 5: chat → scheduled calendar (20:51)

Replaced `ChatDemo` (the "Ask anything about your project" card) with
`CalendarDemo` in `landing/landing-page.tsx`: a static November 2026 grid with
three coloured event dots and a project/platform/time detail square on hover.

- Colours stay in the old chat's fuchsia family: fuchsia-500, violet-500,
  rose-500.
- Feature entry copy updated to match scheduling (was "Ask anything…").
- The dot is an **absolutely-positioned `<button>`**, not a flex item, so the
  `size-*` transition isn't clamped by a flex item's min-content size, and it
  grows symmetrically around the cursor without flicker.

## 5. Sidebar icon + calendar refinements (20:59)

- **Icon corrected:** the `ConstellationIcon` request was for the **sidebar**
  "Creator library" item, not the card thumbnail.
  - `layout/app-shell.tsx`: NAV "Creator library" `Bookshelf03Icon` →
    `ConstellationIcon`.
  - `projects/project-card.tsx`: thumbnail fallback reverted
    `ConstellationIcon` → `FileVideoIcon` (the `rounded-t-lg` fix stays).
- Landing: copy → **"Schedule your posts from within the app"**; removed the
  "Hover a day to preview" footer; auto-play loop added; dot moved to a badge;
  morph sped up.

## 6. Calendar badge, brand SVGs, arrows (21:15)

- **Dot is now a badge hugging the date**, not the cell corner: the day number
  and the dot share an inline span, and the button is anchored `-top-1 -right-2.5`
  relative to the number, so it sits just off the date's top-right and no longer
  floats far away or covers the number.
- **Brand SVG beside the platform name** in the expanded square: each
  `ScheduledPost` gained a `logo` (`/youtube.svg`, `/tiktok-mono.svg`,
  `/instagram.svg`), rendered in a tiny white chip next to the uppercase name.
- **Auto-play demos only day 5** (`CAL_AUTOPLAY_DAY = 5`) — the earlier "random"
  was meant to be this one date. Manual hover/focus still wins; loop idles under
  `prefers-reduced-motion`.
- **Unicode arrows → icon components.** New shared
  `components/common/inline-arrow.tsx` (`ArrowRight01Icon`, text-aligned). All
  rendered arrows replaced:
  - `components/accounts/text-platform-connections.tsx` (two instruction
    paragraphs; the placeholder was reworded since a `placeholder` can't hold an
    icon)
  - `components/landing/landing-background.tsx` ("EN → HI")
  - `components/landing/landing-page.tsx` (`DERIVS.meta` is now a `ReactNode`
    so the Captions entry can embed the icon)
  - `components/projects/draft/draft-context-panel.tsx`
  - `app/data-deletion/page.tsx` (`&rarr;` entity)
  - Remaining arrows are all in code comments (not rendered) and were left.
  - Backend/contracts/corpus arrows are comments/docstrings/prose, not UI.

## 7. Calendar demo: logo in the middle gap, hover-only loop (21:33)

- **Brand logo moved off the start of the text.** It was inline before the
  platform name (`[logo] YOUTUBE`). It now sits centered in the card's empty
  middle gap, between the project name and the date line, in a slightly larger
  white chip (`size-5`). The platform name, project, and date are plain text.
- **The demo loop is hover-only**, matching the other landing demos: the effect
  is gated on the `active` prop (card hover), so day 5 no longer opens on its
  own while the card is idle. Open state is derived
  (`hoverDay ?? (active ? demoDay : null)`) instead of clearing state in the
  effect — oxlint's `react(set-state-in-effect)` rejects synchronous setState.

Verified: `oxlint` + `tsc --noEmit` clean, dev server recompiled, `GET /` 200.
Uncommitted (user didn't ask to commit this round).

---

## Verification throughout

`bun run lint` (oxlint) and `bunx tsc --noEmit` clean after every step; dev
server hot-compiled cleanly; `/`, `/dashboard`, `/library`, `/settings`,
`/data-deletion` all 200. No tests added (repo rule). No secrets touched.

## Not done / next steps

- Nothing on the landing below-the-fold was re-screenshotted here; the landing
  renders behind the client-side auth gate so SSR only returns the loader.
- Calendar month/dates remain hard-coded (November 2026).
