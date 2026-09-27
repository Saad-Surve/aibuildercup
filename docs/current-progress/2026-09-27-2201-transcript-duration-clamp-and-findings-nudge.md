# Progress — transcript length clamp + findings nudge (2026-09-27 22:01)

Two follow-ups requested after `2026-09-27-2146-truth-reviewer-google-search-grounding.md`.

## 1. Corrupt STT timestamps past the video end (big-ai.mp4)

`fixtures/media/big-ai.mp4` is 17.2 min (ffprobe: 1032.47 s). Running Chirp 3 on it directly
reproduced the bug: among 3,268 words the service emitted corrupt offsets -

- `to` at start 2,786,000 ms (46.4 min), end 2,827,000;
- `be` at start 2,827,000, end 698,000 (end **before** start);
- and at least one word ending at 8,099,000 ms (135 min) from a normal start.

Those produced transcript segments past the end of the video (the "44 minute segment").

Fix, in the transcription path:

- `video_tools.probe_duration_ms(source)` reads the true media duration with ffprobe
  (`ffprobe -show_entries format=duration`), against a short-lived signed URL so nothing is
  downloaded. Never raises; returns None when ffprobe is missing/unreadable.
- `transcript_service.sanitize_word_timings(words, duration_ms)` drops words whose start is past
  the duration (plus 1 s tolerance) and clamps any end past it. Without a probed duration it
  estimates one from the 99th percentile of the word ends, capped below the last two values so a
  couple of corrupt timings cannot drag it up, with a generous 60 s margin.
- `transcribe_worker` probes the source duration, sanitizes the words before `build_segments`,
  and passes the real duration to `TranscriptService.save` (new `duration_ms` argument). The
  stored transcript duration is now the media duration, so the heatmap cannot outrun the player.

Verified against the real fixture: probed 1,032,470 ms; both probe and fallback drop the two
over-duration words and no word/segment exceeds the duration (last segment ends at 17.1 min).
Config: `FFPROBE_PATH` (default `ffprobe`).

## 2. Nudge the reviewers so footage does not suppress findings

The visual-tools prompt ("fetch footage ... produce the final findings") correlated with fewer
findings (an earlier project went 14 -> 9 across six reviewers). `VISUAL_TOOLS_PROMPT` gained a
`COVERAGE` paragraph: footage is an aid, not a gate - report every genuine issue the window
covers, report transcript-justified findings whether or not footage was fetched, adjust severity
rather than dropping a finding, and do not stop at the first finding.

**Honest A/B result:** on project `e6c4b7037edb408e9617aa7c1e9b16a7` the per-dimension finding
counts were **unchanged** before/after the nudge (truth 1, clarity 2, pacing 3, legal 2, cultural
2, platform 2 = 12 both). So on that content the model was already at its coverage ceiling; the
nudge is a guardrail against the footage-gating behaviour rather than a proven boost. Worth
re-checking on longer / visually driven videos, and the earlier 14 -> 9 drop may partly be
run-to-run variance.

## Verification
- `ruff` + `mypy` clean (70 files); web unchanged this round.
- Duration clamp: real ffprobe on the fixture + the exact corrupt word timings from a live Chirp
  call; both the probe and fallback paths pass.
- Findings nudge: one real API analysis run compared against the prior run on the same project
  (counts identical; see above).

## Notes / gotchas
- Clamping a corrupt `endMs` to the media duration can enlarge the segment that contains it; in
  real dense speech that segment is a normal cue near the end, but the sanitizer also drops words
  whose start runs past the end, which is what removed the phantom 46-minute segment.
- `big-ai.mp4` STT was run through a temporary `.../scratch/transcribe-tmp/` object that was
  deleted after inspection.

## Not done / next steps
1. Both this and the grounding work are **uncommitted** (see `git status`).
2. Deploy the API for the FFprobe clamp and grounding to exist in prod.
3. Re-run a long, visually-driven video to confirm the coverage nudge matters there.
