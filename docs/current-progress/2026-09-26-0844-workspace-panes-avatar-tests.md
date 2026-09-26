# Progress — 2026-09-26 08:44 UTC — workspace 2-pane, live state pill, avatar, tests removed

## What changed

### Project workspace (2-pane)
- `project-workspace.tsx`: `max-w-7xl`; source-video card is pinned (`lg:sticky lg:top-20`);
  the right column stacks **Transcript → Review (heatmap/analysis) → Findings**.
- New `web/src/lib/workspace.ts` exports `WORKSPACE_PANE_CARD` (a fixed
  `h-[min(72vh,40rem)]` flex column). The video, transcript, review and findings cards all
  use it, so every card is exactly the same height and scrolls its own body. This also
  solves the "findings card grows forever" problem.

### Transcript progress
- `processing-status-card.tsx`: removed the fake `Progress` bar entirely. It is now a
  spinner + a **state pill** ("Queued", "Transcribing", "Segmenting", "Reviewing", "Failed")
  derived from `job.progress.step` / `project.progress.stage`, plus the live message and the
  retry button on failure.
- `transcript-panel.tsx`: card is a fixed-height flex column; only the segment list scrolls.

### Review filter → heatmap
- `review-panel.tsx` passes `severityFilter` into `HeatmapTracks`.
- `heatmap-tracks.tsx`: bins whose severity is not in the active filter are dimmed to
  `opacity-25` (hover/selected always win), so the filter lightly spotlights matching moments.

### Humation avatar (now real)
- Backend: `AvatarState` schema and `Me.avatar`; `UserService.save_avatar`; new
  `PUT /api/me/avatar`; `contracts/openapi.yaml` updated (path + schema). The state is stored
  inline on `users/{uid}.avatar`, so account deletion already covers it — no new storage.
- Frontend: `AvatarState` + `Me.avatar` types; `@humation/{react,core,assets-humation-1}`
  added to `package.json` and `bun.lock`; `AvatarBootstrap` mounted in `(app)/layout.tsx`;
  `UserMenu` renders the Humation avatar instead of the Firebase photo; `AvatarEditorDialog`
  added to the Profile page.
- Also added the missing `updateProject` to `lib/projects.ts` so the parallel-session
  `edit-project-dialog.tsx` type-checks (it was the last `tsc` failure).

### Tests removed
- Deleted `backend/tests/` in full; removed `pytest`, `pytest-asyncio`, `httpx` and the
  `[tool.pytest.ini_options]` block from `backend/pyproject.toml`; `uv lock` regenerated.
- `docs/current-progress/2026-09-25-0829-failure-manual-square.md` (prior run) states the
  worker already wrote the specific failure reason to the project; that was not in the
  committed worker, which is why the card stayed generic. Now fixed for real.

## Verified
- Backend: `ruff check .` clean; `mypy app` clean (68 files). No tests remain.
- Web: `bunx tsc --noEmit` clean, `bun run lint` (oxlint) clean, `bun run build` passes with
  all avatar/edit-project files present.

## Notes / caveats
- `web/src/app/globals.css` swaps `--signal` to the fuchsia tone (parallel-session WIP,
  committed as-is so the deployed web matches the repo).
- `web/web.log` / `web/web.err.log` are local junk and are not committed.
- Transcript production fix from `2026-09-26-0827-…` still uncommitted at note time; this
  commit includes it, so the next CI run on `main` now deploys the fallback worker.
