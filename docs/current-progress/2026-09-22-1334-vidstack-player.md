# Progress — 2026-09-22 13:34 UTC — Vidstack studio player

Replaced the native `<video>` element in the workspace with a Vidstack v1 custom layout
skinned in the app's design tokens. Uncommitted (not requested).

## What changed

- **`@vidstack/react@1.15.6`** added (`@next` tag — `latest` still resolves to the old 0.6.x
  line, which needs React 18; 1.x supports React 19, verified via the project's changelog).
- **`source-video-player.tsx` rewritten** around headless Vidstack parts:
  - `MediaPlayer` + `MediaProvider` (blob or signed-URL src, native `poster` attr, `playsInline`,
    `preload="metadata"`, auto-hiding controls via `controlsDelay` + `hideControlsOnMouseLeave`).
  - Custom control bar: play/replay, ±10s skip (Hugeicons `GoBackward/Forward10Sec`), tabular
    `current / duration` readout (same `formatTimestamp` as the transcript panel), mute +
    volume slider (desktop only), PiP and fullscreen buttons that render only when the
    capability exists.
  - Center overlay: signal-blue circular play/replay button when paused, design-system
    `Spinner` while buffering, click-anywhere-to-play via a `toggle:paused` gesture.
  - Tooltips on every icon button, sentence-case labels, full keyboard shortcuts (player
    defaults), dark-mode safe (white-on-video chrome).
  - Kept behavior: local-blob-first src resolution, poster pipeline, failure card, skeleton,
    and transcript `creator-studio:seek` events (now via the player instance).
  - Caption `<track>` still pending — backend stores the VTT but serves no caption URL yet.
- **`source-video-player.css` (new):** slider geometry only (fill/buffered widths from
  `--slider-fill`/`--slider-progress`, thumb show/grow on `data-active`/`data-dragging`,
  signal focus ring, popover-styled hover timestamp bubble). Layout stays in Tailwind.
  Only `base.css` imported from Vidstack — no default theme.

## Verification

- `oxlint` clean, `eslint` 0 errors (1 pre-existing `<img>` advisory), `oxfmt` applied,
  `bun run build` passes (TypeScript in build validates all Vidstack API usage).
- Gotchas hit while building (for the record):
  - `bun add @vidstack/react` installs 0.6.x; v1 lives on `@next`.
  - oxlint `react(immutability)` forbids assigning to `useMediaPlayer()` results
    (`player.currentTime = …`, `player.muted = …`). Used `useMediaRemote()` method calls
    (`seek`/`mute`/`unmute`) instead; the `playerRef` seek in the transcript effect is fine
    because refs are mutable by design.
  - `Controls.Root` takes no hide props — auto-hide is player-level props; `[data-visible]`
    styling replicated from the default theme (read from `node_modules`, not guessed).

## Not done

- Backend transcription trigger (previous note) — still the next backend step before any demo.
- Visual check in both themes + mobile still needs a human pass (no screenshot tooling here).
