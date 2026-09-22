# Progress — 2026-09-22 13:41 UTC — video.js player

User verdict on the Vidstack custom build: looks bad. Swapped to video.js 8 (default theme +
signal accents) instead of hand-rolling player CSS. Uncommitted (not requested).

## What changed (`web/` only)

- Removed `@vidstack/react@1.15.6` (`bun remove`); added **`video.js@8.24.1`** (ships its own
  types, so no `@types` package).
- **`source-video-player.tsx` rewritten** on video.js:
  - Player created in an effect via dynamic `import("video.js")` — nothing player-related
    evaluates during SSR/prerender. Disposed on unmount (StrictMode-safe).
  - Options: controls, `preload: metadata`, fluid 16:9, `playsinline`, responsive bar,
    poster, `{ src, type }` sources, rates `[0.5, 1, 1.25, 1.5, 2]`, inline volume panel.
    Default control bar otherwise (play, volume, time/divider/duration, seek bar with hover
    tooltip, rate menu, PiP, fullscreen, auto-hide).
  - Kept behavior: local-blob-first src (IndexedDB/offline), poster pipeline (pushed via
    `player.poster()` when the captured frame lands after mount), failure card, skeleton,
    transcript `creator-studio:seek` events (`player.currentTime(…)`), captions `<track>`
    placeholder (oxlint `media-has-caption` requires it; real cues still need the backend
    caption URL).
- **`video-player-skin.css` (new):** only accents over the default theme — signal progress
  fill, signal big-play button, signal menu selection, mono tabular time, signal focus ring.
  Deleted the Vidstack skin file with the swap.

## Verification

- `oxlint` clean, `eslint` 0 errors (1 pre-existing `<img>` advisory), `oxfmt` applied,
  `bun run build` passes (TypeScript included).
- Gotchas:
  - `bun add @vidstack/react` resolves 0.6.x; v1 is on `@next` (from the previous note).
  - video.js has no named `VideoJsPlayer` type export — typed the ref as
    `ReturnType<typeof videojs>`.
  - A stray `bun add` at the repo root created root `package.json`/`bun.lock`/`node_modules`;
    deleted immediately. Run `bun` only in `web/`.

## Not done

- Human visual pass (both themes, mobile) — still no screenshot tooling here.
- Backend transcription trigger — still the next backend step before any demo.
