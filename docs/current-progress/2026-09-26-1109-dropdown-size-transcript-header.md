# Progress — 2026-09-26 11:09 UTC — dropdown sizing + transcript header duration

## Transcript card header
- Removed the duration (`formatTimestamp(transcript.durationMs)`, the "4:00") from the
  Transcript card meta line. It now reads `N segments · <language> [· N speakers]`.
  `formatTimestamp` is still imported — it is used for the per-segment row timestamps.

## Version / review dropdowns
- The shared `SelectContent` no longer aligns the selected item over the trigger
  (`alignItemWithTrigger = false`). With the native-style overlay the small `w-20` version
  triggers squashed the popup against the trigger and it read as a tiny/awkward dropdown;
  it now opens as a normal menu below the trigger (still `min-w-36`).
- Both version pickers render their value explicitly through `SelectValue`'s render prop:
  - Transcript: `v{version}` (placeholder "Version").
  - Review: `v{runs.length - index}` for the selected run (placeholder "Latest"), matching
    the item labels exactly.
- These were sitting uncommitted in the working tree from the previous session; the duration
  removal above was the missing half of the request.

## Verified
- Web: `bun run lint` (oxlint) clean, `bunx tsc --noEmit` clean.
- `bun run build` passes. Note: on this machine the first attempt OOM'd the default Node heap;
  re-running with `NODE_OPTIONS=--max-old-space-size=6144` builds clean. Not a code issue.

## Not done / next
- Nothing outstanding for this request. Local junk logs (`debug.log`, `web/web.log`,
  `web/web.err.log`) deleted, not committed.
