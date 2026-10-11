# 2026-10-11 23:41 — Substack bookmarklet, slot status card, calendar full width

## 1. Substack one-click cookie (committed earlier as `6c85dce`)

A draggable **Copy Substack cookie** bookmarklet in the connect dialog
(`web/src/components/accounts/text-platform-connections.tsx`). It reads
`substack.sid` on a Substack tab and copies it to the clipboard, so the creator
never opens devtools. Doc updated. No more manual cookie hunting.

## 2. Slot status on the card, read-only

The status was removed as an editable dropdown; it is now shown — automatically
and **not editable** — on the slot card itself (`calendar/schedule-dialog.tsx`):
the edit header shows the title plus a status `Badge` (`Planned`/`Scheduled`/
`Published`/`Cancelled`) with the note "Status is automatic — it follows the
upload, not a setting." The calendar chips already carried the same label.

## 3. Calendar layout: full width + Upcoming as a view

`web/src/app/(app)/calendar/page.tsx`:
- **Removed the right-hand "Upcoming" sidebar** and the two-column grid wrapper
  (`lg:grid-cols-[minmax(0,1fr)_280px]`) that was squeezing the calendar.
- The page no longer caps at `max-w-6xl`; the calendar card now spans the
  content area.
- **`Upcoming` is now a view** in the Month / Week / Day toggle: `CalendarView`
  gained `"upcoming"`, with a 90-day window (`windowFor`), `titleFor` → "Upcoming",
  `stepCursor` → ±30 days, and a full-width list render (status dot, logo,
  project · date/time, status badge). The old `upcoming` memo no longer slices
  to 8.

## Verification

- `oxlint` + `tsc` clean; `eslint` 0 errors (pre-existing `<img>` warnings only);
  full `next build` OK; `/calendar` 200.
- Not visually screenshotted (client-rendered behind auth).

## Notes

- The first change (bookmarklet) was committed locally on request as
  `6c85dce`; the layout/status change is committed separately. Neither is
  pushed yet.
