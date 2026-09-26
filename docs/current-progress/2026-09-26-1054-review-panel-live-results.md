# Progress — 2026-09-26 10:54 UTC — review panel: results appear without a reload

User report: the review panel shows the run as started, but the heatmap/findings only
appear after a manual refresh.

## Root cause (client query orchestration, no backend change)

Two defects in `web/src/components/projects/review-panel.tsx`:

1. **`isRunning` was read from the runs *list*, which never polls.** The list
   (`["analysis-runs"]`) was fetched once and only invalidated on "Run analysis".
   So the flag that gates the reviewers/heatmap/findings intervals never left the
   value it had at start. Worse, when the list *did* refresh (window focus /
   reconnect), it could flip to a terminal status and **stop the derived queries
   before they fetched the final data**.
2. **The last poll could be dropped.** Findings and heatmap bins are written
   microseconds before the run flips to `ready`; the interval queries stop the
   instant the run settles, so the one poll that would have picked up the output
   was never guaranteed to run.

Together: a stale `isRunning` (stuck "Reviewing", disabled Run button, forever
polling) or a race that stopped polling a beat too early, with nothing forcing a
final fetch — hence "refresh and it appears".

## Fix (`web/src/components/projects/review-panel.tsx`)

- `isRunning` is now derived from the **freshest** run (`runQuery.data ?? list row`)
  via a shared `isInFlight` helper, so polling decisions cannot disagree with the
  status the header shows.
- The runs **list now self-polls** every 4s while any listed run is in flight, so
  the Run button, reviewer counter and dropdown stay accurate. It stops when no
  run is in flight.
- Added a one-shot **settle effect**: on the in-flight -> settled transition for a
  run, invalidate reviewers/heatmap/findings once. `settledRunRef` guards against
  repeats and per-run loops. This guarantees the final output lands even if the
  interval stopped first.
- `runQuery` uses the same `isInFlight` predicate (behaviour unchanged).

No contract, schema, or backend change.

## Verified

- Web: `bunx tsc --noEmit` clean, `oxlint` clean, `bun run build` passes,
  `bun run lint:eslint` 0 errors (1 pre-existing `<img>` advisory).
- Backend untouched.

## Not done / next step

- This was reasoned from the query code + prior poll-fix notes
  (`2026-09-25-1648-transcript-404-stuck.md`, `2026-09-25-1706-cdn-cached-404.md`);
  **not yet reproduced live** against a real analysis run. Worth one pass: start a
  run, switch tabs mid-run, return — the heatmap and findings should populate
  without a reload.
- If it still sticks, the next suspect is the SSE stream for the analyze job
  (the workspace tears SSE down once the project is `ready`, so analysis has no
  push path today).
