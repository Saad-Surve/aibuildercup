# Real creator videos: recall of admitted errors

Four creator-published CC BY videos, **five known corrections**, and local ASR transcripts.
This is an independently authored, partial-gold evaluation set. Gold consists only of errors
the creators themselves acknowledge in their YouTube descriptions and whose wrong statements
can be located in the audio. There are no planted errors and no clean controls.

Every label has `partialGold: true`. The headline measure is recall of these five known errors,
with the existing Wilson interval, medium-or-higher and time-only variants, timing errors and
paired issue overlap. **Precision is unavailable:** an unmatched finding may identify a real,
unlabelled issue. Finding counts are descriptive, not false-positive counts. This set cannot
measure overall editorial quality, exhaustive error detection, edit usefulness, safety, or
performance across creators: three of four videos come from one channel, and all are English.
Creator corrections are a partial answer key, not independent verification of every assertion.

## Licence and attribution

Each licence was re-verified from live yt-dlp metadata on 14 October 2026, with the exact value
`Creative Commons Attribution license (reuse allowed)`. [manifest.json](manifest.json) records
channel, title, URL, upload date, full public description, exact correction note, verification
time, resolution and downloaded-media SHA-256. Current [YouTube licence guidance](https://support.google.com/youtube/answer/2797468?hl=en)
links [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/); the metadata text does not state
a version. Keep the creator, title, source URL and licence link with any displayed footage or
redistributed transcript, and identify changes. Videos were downloaded/remuxed at 720p without
editorial edits. Transcripts are machine-generated adaptations and may contain ASR mistakes.

| Creator | Video / source | Upload date | Downloaded duration | Licence verified |
|---|---|---|---:|---|
| vlogbrothers (John Green) | [Is Book Publishing Dying? An Author's Perspective](https://www.youtube.com/watch?v=BBvze0lGcZg) | 2025-10-21 | 6:16.906 | CC BY |
| vlogbrothers (John Green) | [Henry](https://www.youtube.com/watch?v=JhVJMO0wgTE) | 2023-08-15 | 7:00.560 | CC BY; evaluation only |
| Gavin Davies Music | [Autotune and Pitch Correction - explained for the music listener in - plain English](https://www.youtube.com/watch?v=FqYg-gjCrPw) | 2026-09-17 | 16:04.696 | CC BY |
| vlogbrothers (John Green) | [Ukraine and Russia: What Caused the War?](https://www.youtube.com/watch?v=mMZYKxgc9TE) | 2022-03-15 | 8:55.290 | CC BY |

**Henry is evaluation-only: never use it on screen, in a public demo or in promotional footage.**

## Known corrections

Descriptions and issue `source.quote` preserve the creator's exact text, including the spelling
`befaquiline` in the Henry note. The ASR also has spelling errors (for example `bodaculin` in
the spoken Henry claim); the transcripts have not been silently corrected.

| Video | Known error | Primary audio span | Other occurrences of the same issue |
|---|---|---|---|
| `BBvze0lGcZg` | Black Ops 6 versus the entire Call of Duty franchise's sales | 0:25.440–0:36.640 | none |
| `JhVJMO0wgTE` | Henry described as the first recipient of a bedaquiline-based cocktail | 4:15.360–4:21.460 | none |
| `FqYg-gjCrPw` | Software year stated as 2015; creator corrects it to 2019 | 5:18.460–5:21.180 | 1:21.200–1:26.500; 14:15.540–14:18.900 |
| `mMZYKxgc9TE` | Ukrainian and Russian described as national languages | 0:16.800–0:26.160 | none |
| `mMZYKxgc9TE` | Ukraine's etymology presented as definitely “borderlands” | 4:21.820–4:27.340 | none |

The hero's audio says the individual game outsold all US adult books in 2024; it does **not**
say “500,000,000.” That number comes from the creator's correction. Label the spoken comparison,
not an invented spoken number. The software-year repetitions are one logical issue with
`additionalSpans`, so they cannot inflate the denominator. Ukraine's third description note,
“Thirdly, I  misspelled Kyiv as Kiev.”, concerns spelling on screen and is excluded because it
cannot be located as a wrong statement in the audio. No other editorial issues were invented.

## Pre-registration

**These labels were committed on `feat/editorial-real` before any model reviewed the videos.**
The pre-registration commit is the commit that introduces this README, matching rule, manifest,
labels and transcripts; use the hash reported by the implementation agent or the command below.
Local Whisper performed transcription only. There have been **zero Gemini calls, zero review-arm
runs and zero cloud STT calls** on this set during preparation. Prompts were neither opened nor
tuned. Only the coordinator runs the new set after labels are committed and prompts are frozen.

```bash
git log -1 --format=%H -- evals/editorial-real/labels evals/editorial-real/transcripts \
  evals/editorial-real/matching.json evals/editorial-real/manifest.json
```

The matching file is copied **byte for byte** from the dev set (SHA-256
`43a7c21d16ab76f5918404bc9a08bc953f9908a793c738f3a605dc94c4d5d7c0`). All five categories are
`factual_error` with `truth_evidence` as expected dimension. The existing 5-second, one-to-one
time/dimension matcher is unchanged. It does not check semantic equivalence, so a broad nearby
finding can match an error without accurately describing it; inspect matched evidence before
claiming factual-error detection. Briefs/audience are neutral inferences, explicitly marked as
such, and omit correction notes. The runner does not send issue labels or the manifest to models.

Future creator/editor labels use [HUMAN-LABELS.md](HUMAN-LABELS.md) for the three non-sensitive
videos and belong in a **separate, dated commit**, disclosed separately from this answer key.
Changing gold after a run invalidates comparisons to the original labels.

## Local files and coordinator handoff

`labels/<YouTube-id>.json`, `transcripts/<YouTube-id>.json`, `matching.json` and `manifest.json`
are committed. Media and full yt-dlp/word-timing dumps live under the gitignored
`fixtures/media/editorial-real/`; no media is committed or uploaded. Each label's relative media
path resolves from this dataset root. On this worktree all four MP4 files are present at 720p.
Transfer these exact local files if the coordinator uses another worktree: a fresh download can
change bytes, and the live runner verifies media against the committed hashes before any call.
Replay remains possible without the ignored media. `manifest.json` participates in the runner's
pre-registration hashes/dirty check. Existing dataset roots and full-gold scores are unchanged.

Six top-level yt-dlp metadata extraction attempts verified four videos; two extra attempts were
needed for Gavin's missing licence/channel metadata. Four downloads used saved info JSON, making
no additional metadata extractions. **Zero new search requests**: the fourth eligible video was
found in the supplied cached scan. Internal yt-dlp HTTP requests are not counted/observable here.
No throttling response was observed; retries were disabled and metadata requests were sparse.

Local transcription uses the interest collector's MLX Whisper approach, with previous-text
conditioning disabled, word timestamps enabled and an explicitly pinned model revision. Only
segment timestamps/text are committed, in the harness's normal millisecond JSON layout. Gold
spans were located by inspecting those segments and local word timings; they are not human-audited.

To transcribe existing downloaded media (skips existing transcripts; no YouTube/cloud requests):

```bash
cd backend
uv run --with mlx-whisper python ../evals/editorial-real/transcribe.py \
  BBvze0lGcZg JhVJMO0wgTE FqYg-gjCrPw mMZYKxgc9TE
```

For the coordinator, pass `--root ../evals/editorial-real` to the existing harness from `backend/`.
No run command was executed during preparation. See [DEMO.md](DEMO.md) for the hero and its
later manual app upload. Human usefulness and demo behaviour remain unverified until that work.
