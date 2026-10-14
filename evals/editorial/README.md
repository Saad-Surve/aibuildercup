# Editorial evaluation: why not just ask Gemini?

A gold-issue benchmark for the review heatmap. Five short videos carry **20 planted flaws** and
one **clean control**. Three arms review the same videos with the same Gemini model, and each
is scored against labels that were committed before any model ran.

| Arm | What it is |
|---|---|
| `baseline` | One Gemini call over the whole video plus its transcript, asked for timestamped issues in the reviewers' output shape. Google Search grounding on, like the Truth reviewer. |
| `rubric` | The same single call, with all nine reviewers' rubrics pasted in. This is the strongest "just ask Gemini" baseline, and it isolates specialisation from prompt content. |
| `reviewers` | The production path: transcript chunking, shared frames, footage tools, nine reviewers, per-window normalisation. It reuses `analysis_coordinator`, `reviewer_base` and the worker's frame sampler. It is not a reimplementation. |
| `adjudicated` | The same `reviewers` findings, checked by the production footage-backed adjudicator. Rejections are excluded and downgrades use adjusted severity for scoring. |
| `edited` | The same reviewers, then the production `editor-v1` consolidation pass. Drops and merges leave the scoring set; originals remain in raw output. |
| `edited_adjudicated` | Reviewers → editor → footage adjudicator; reuse joins historical adjudicator verdicts by surviving original finding ID. |

Results are reported per arm and never pooled across arms. The first four-arm run is
`editorial-2026-10-14-flash38`; the post-hoc editor development run is disclosed below.

A second, independently authored held-out set lives in `evals/editorial-heldout/`
(see its README); nobody runs any arm on it until the coordinator does so after the
editor pass is frozen. A third, independently authored long-form set (10-14 minute
videos with subtler flaws) lives in `evals/editorial-longform/` (see its README);
the same no-run rule applies to it.

## Layout

| Path | Contents |
|---|---|
| `scripts/<id>.json` | The spoken script: lines, voice, planted flaws and the lines that carry them. Hand-authored. |
| `media/<id>.mp4` | The video the arms review. Committed so the bytes are pinned (about 4 MB in total). |
| `transcripts/<id>.json` | Transcript segments from the production segmenter. |
| `labels/<id>.json` | Gold labels: source, duration, and each issue `{id, category, startMs, endMs, additionalSpans, description, expectedDimension}`. Clean controls have an empty `issues` list. |
| `matching.json` | The pre-registered matching rule and the category-to-dimension table. |
| `../results/editorial-<run>.raw.json` | Every raw model response, normalised findings, tokens and per-call records from a live run. |
| `../results/editorial-<run>.json` and `.md` | The scored result and its markdown tables. |

Code is in `backend/scripts/`: `editorial_build_media.py` (build), `editorial_eval.py`
(runner, replay, report) and `editorial_score.py` (matching and metrics; pure, no network).

## How the videos were made

They are **constructed**, not recorded. `editorial_build_media.py` renders each script line with
macOS `say` (a different voice per video), places the audio on a timeline with exact pauses,
and burns the title and captions onto a plain 640x360 card with FFmpeg. Because the timeline is
built, every issue span is exact to the millisecond: the label start and end are the measured
start of the first and end of the last tagged line. No STT is involved, so the same ground-truth
transcript goes to every arm. The category, description and expected dimension of each flaw
are authored in the script; the builder only measures time.

| Video | Length | Spoken as | Planted flaws |
|---|---:|---|---|
| `espresso-basics` | 2:23 | Samantha | A1 weak hook 0:00-0:20, A2 jargon 0:42-1:00, A3 tangent 1:13-1:50, A4 US-only units and stores 1:57-2:09, A5 missing newsletter CTA 2:19-2:22 |
| `immune-system-cold` | 2:23 | Karen | B1 head-heat myth 0:37-0:43, B5 unexplained immunology jargon 1:01-1:16, B4 antibody definition repeated four times 1:17-1:42, B2 unsourced vitamin C claim 1:53-2:00, B3 dangerous child-fever advice 2:00-2:11 |
| `index-fund-mistakes` | 2:05 | Daniel | C4 US-only accounts 0:30-0:41, C2 "beat 90% every year" 0:56-1:05, C5 condescending tone against a warm brief 1:19-1:31, C3 guaranteed returns and emergency savings 1:32-1:43, C1 promises three mistakes, delivers two 1:44-1:53 (also the promise at 0:08-0:15) |
| `python-decorators` | 2:32 | Moira | D1 vague opening 0:00-0:15, D2 wrong Python version 0:25-0:35, D4 function re-explained 0:35-1:03, D3 tabs-vs-spaces rant 1:34-2:12, D5 caching decorator promised and never built 2:16-2:24 (also the promise at 0:16-0:24) |
| `boiled-egg-control` | 2:00 | Tessa | none: a short, correct, well-structured video with a CTA that matches the brief |

Categories: weak_hook x2, jargon x2, tangent x2, pacing_drag x2, factual_error x2,
unsupported_claim x2, safety x2, broken_promise x2, locale_assumption x2, missing_cta x1,
tone_mismatch x1. Together they exercise all nine reviewers' dimensions except emotional impact,
which is only accepted as a secondary dimension (see `matching.json`).

The planted health and finance statements are deliberately wrong or unsafe. The videos are test
fixtures, not publishable content. Every video carries a title, platform, audience and brief that
all arms receive; the briefs state the creator's goal, which is what makes a missing CTA or a tone
mismatch a defensible label.

Rebuild (no network, no model calls; overwrites media, transcripts and labels, so the media
hash changes if the macOS `say` or FFmpeg version differs):

```bash
cd backend && uv run python scripts/editorial_build_media.py            # all
cd backend && uv run python scripts/editorial_build_media.py --only boiled-egg-control
```

**Not built:** a recorded set. Natural flaws (a creator actually stumbling, real STT errors,
visual mistakes) need a human to record them. To extend the benchmark, add a recorded video,
write its transcript to `transcripts/<id>.json` (STT or hand-corrected), hand-write
`labels/<id>.json` in the same format with `source.kind: "recorded"`, commit, then run.

## Pre-registration

The labels, transcripts, media, scripts and `matching.json` were committed before any model saw
the videos. The runner enforces it:

- `run --execute` refuses to start when any of those paths have uncommitted changes
  (`--allow-dirty-labels` exists for smoke tests only).
- Every raw and scored result records `labels.commit` (the last commit that touched those paths),
  their SHA-256 hashes, the matching-rule hash and the code revision. A scored file also states
  whether the labels changed since the run (`labelsUnchangedSinceRun`).
- **Pre-registration commit: `2e1357166373beb3d44765c7990311cba4f74f7d`.** Quote the commit in
  the results table; if the labels change after a run, the run is void.

What is fixed in advance: the videos and labels, the matching rule (below), the headline metric
(recall and precision over all non-strength findings), the secondary variants (severity at least
medium; time-only), and the prompts (`reviewers-v5`, `editorial-baseline-v1`). Prompts and rules
must not be edited after the first scored run for confirmatory evaluation. The five original
videos were explicitly redesignated as a development set before editor tuning; those results
are post-hoc, and the editor is frozen before the coordinator runs independent held-out data.

## Matching rule

A finding is an **issue finding** when its severity is not `none`; strengths are ignored. It
matches a gold issue when both hold:

1. **Time:** its `[startMs, endMs]` is within **5 s** of the issue's span (or any
   `additionalSpans` entry). A gap of zero means the spans overlap.
2. **Dimension:** its dimension is the issue's `expectedDimension`, or one of the dimensions
   listed for the issue's category in `matching.json`. Example: a `jargon` issue accepts
   `clarity` and `audience_brand`; a `factual_error` accepts only `truth_evidence`.

Matching is **one-to-one and greedy**: candidate pairs are ordered by (overlapping before merely
near, expected dimension before compatible, smaller gap, smaller centre distance); each issue
and each finding is used at most once. A second finding on the same issue is a false positive,
so duplicates cannot inflate recall or precision. Where two issues sit within 5 s of each other
(B2/B3, D2/D4, C3/C5) a finding can only match one; ties go to the expected dimension.

## Metrics

| Metric | Definition |
|---|---|
| Recall | matched gold issues / 20, with a 95% Wilson interval. n=20 is small: read the interval. |
| Precision | matched findings / issue findings on the flawed videos. **A lower bound:** unplanted real problems (and nitpicks) count as false positives, because only planted flaws are labelled. |
| Variants | `headline` (all issue findings), `actionable` (severity at least medium), `timeOnly` (dimension ignored). The gap between `headline` and `timeOnly` shows how often an arm found the right place and called it the wrong thing. |
| Timestamp error | absolute difference between the finding's start and the issue's nearest span start, over matched pairs (median, mean, max). |
| Clean control | issue findings on `boiled-egg-control`, as a count and per minute, for each variant. The control is not provably flawless: a strict reviewer may raise a fair nitpick (the smoke test did), so compare arms, not against zero. |
| By category | recall per category. |
| Cost and calls | per arm: model requests, input and output tokens (output includes thinking tokens), estimated USD, USD per matched issue, failed calls. Search queries are counted but not priced. |
| Paired | gold issues found by both arms, one arm, or neither. |

Cost uses `LLM_INPUT_PRICE_PER_MTOK` and `LLM_OUTPUT_PRICE_PER_MTOK` (the local Flash-Lite tier)
unless `--model`, `--input-price` and `--output-price` are given. For the deployed
`gemini-3.8-flash` configuration pass `--model gemini-3.8-flash --input-price 0.75
--output-price 3.75` (introductory rates, until 31 December 2026). See [docs/costs.md](../../docs/costs.md).

## Running it

All commands run from `backend/` and use the live Gemini API through the production provider.

```bash
# 1. Dry run (the default): arms, videos, bounds on model calls. No model call.
uv run python scripts/editorial_eval.py run --arms baseline,rubric,reviewers --max-calls 200

# 2. Live run. --max-calls is a hard stop: the 201st call raises and the partial raw file is kept.
uv run python scripts/editorial_eval.py run --arms baseline,rubric,reviewers --max-calls 200 --execute

# 3. Re-score saved raw output with zero model calls (labels, rule and normaliser as they are now).
uv run python scripts/editorial_eval.py replay ../evals/results/editorial-<run>.raw.json

# 4. Markdown tables from a scored file.
uv run python scripts/editorial_eval.py report ../evals/results/editorial-<run>.json
```

Call bounds for the five videos (each transcript is one chunk): `baseline` 5, `rubric` 5,
`reviewers` 45 to 135 (nine reviewers, plus up to two footage-tool rounds each), so a full run of
the three arms is 55 to 145 calls. Token volume is small: the smoke test's single baseline call was
14,069 input and 406 output tokens ($0.004 at Flash-Lite rates), and the reviewer arm sends about
nine calls of a few thousand tokens plus six frames per video. Expect cents on Flash-Lite and a
few tenths of a dollar at Flash rates, plus Search queries (the Truth reviewer and the baselines;
5,000 a month are free). Use `--videos id,id` to run a subset and `--no-grounding` or
`--no-visual-tools` for ablations.

`replay` re-normalises the single-prompt arms from their saved raw JSON and re-scores every arm
from saved findings. It does not re-run reviewer normalisation: those findings are stored as
normalised. A replay scored file has `modelCalls: 0` and a `replayOf` hash of its input.

### The adjudicated arm

`--adjudicator module:function` defaults to the production
`app.agents.adjudicator:adjudicate` and is resolved before any live call. Its interface is:

```python
async def adjudicate(findings: list[Finding], *, segments, llm, settings,
                     toolkit, store, budget_usd, creator_context="",
                     reserve_call=None, settle_call=None, abort_on=()) -> AdjudicatorSummary
```

List `reviewers` before `adjudicated` in `--arms`. The arm uses the same reviewers' findings,
so the comparison is paired. It uses the selected `--model`, brief/audience and actual local
frames/clips even when reviewer-requested visual tools are disabled. Up to
`MAX_ADJUDICATOR_CALLS` calls per video (default 12 total, including at most four conflict
checks) are added to the dry-run upper bound; the minimum is zero when no check is needed.
Provider retries are disabled for this pass, and the harness's global call cap aborts it.
Provider/media/validation failures leave findings not checked, as in production.

Raw output saves original observations in `allFindings`, scoring observations in `findings`,
and the pass summary in `adjudicator`. Checked footage is written beside raw results under
`editorial-{runId}.evidence/{videoId}/`; no cloud persistence is needed. Its reported cost is
the reviewers' cost plus the adjudicator's. Prompt version and adjudicator source hash are
recorded for replay. Run this arm with live calls only when explicitly authorized.

## Fairness choices

- Same model, title, platform, audience, brief and transcript for every arm. No persona, for
  every arm.
- The baseline arms get the **whole video**; the reviewers see transcript, up to six frames and
  up to three footage-tool calls, as in production. That favours the baseline, but these videos
  are audio-led so there is little visual content to miss.
- The baseline prompt uses the same 1-5 scale, severity scale and finding schema as the reviewers
  (plus a `dimension` field the model fills itself), and its output goes through the reviewers'
  own validator: timestamps clamped, quotes checked against the transcript, findings without a
  suggestion dropped. Both arms are held to the same output standard.
- Search grounding is on for the baselines and for the Truth reviewer. Pass `--no-grounding` to
  switch both off.

## Limits

- **Constructed, not natural.** TTS speech and flaws written by the system's author, who knows the
  reviewers' rubrics. A flaw written to be found is easier than one a creator makes by accident.
  Treat the numbers as "does it catch clear planted flaws, and does it stay quiet when there are
  none", not as accuracy on real creator videos.
- **Small:** 20 issues, 4 flawed videos and 1 clean control, one run per arm. The intervals are
  wide and run-to-run variance is unmeasured. Repeating the run does not add independent videos.
- **Ground-truth transcripts.** STT errors are not exercised, and neither is Hindi or Hinglish,
  although the product supports them. There is no visual flaw: the visuals are a caption card.
- **Precision is a lower bound** (unlabelled but fair findings count against an arm), and
  severity-weighted usefulness is not measured. Whether an edit is good advice needs human
  judgment: see the blind-editor protocol in [evals/README.md](../README.md#editorial-quality-protocol-not-results).
- **Author-chosen compatibility table.** The category-to-dimension mapping is a judgment made
  before the run. `timeOnly` recall shows how much it matters.
- **Spans of 5 to 40 s** with a 5 s tolerance are generous for tangents and drags, and tight for
  point errors.
- **Counts are logical calls.** A transient retry inside the provider is not counted separately.
- **Smoke test, disclosed:** one `baseline` call on `boiled-egg-control` (no flawed video, so no
  label was seen against model output) validated the pipeline: 1 call, 14,069 input and 406 output
  tokens, two Search queries, one finding normalised cleanly. Its output is not in `evals/results/`.
  The reviewer arm was initially exercised offline for wiring; the later full flash38 run
  supplies the live reviewer findings reused below.

## Editor pass (dev, post-hoc)

These five videos are the **DEV set**. This is post-hoc tuning on known outputs and labels,
not confirmatory evidence, natural-video accuracy, or a held-out result. No held-out data or
branch was read. Label commit remains `2e1357166373beb3d44765c7990311cba4f74f7d`;
`matching.json` is byte-identical (SHA-256
`43a7c21d16ab76f5918404bc9a08bc953f9908a793c738f3a605dc94c4d5d7c0`).

The final frozen run is
[`editorial-2026-10-14-editor-v1-dev`](../results/editorial-2026-10-14-editor-v1-dev.md)
(JSON and raw output committed alongside it). **Frozen prompt version: `editor-v1`**,
editor source SHA-256 `6707201628a12375695ee544eaa76b7ae10a15d0b0fdd69d4c6866e628b1c794`.
Model is `gemini-3.8-flash`, low thinking, input $0.75/M and output $3.75/M.
All four original arms reuse saved flash38 output. Only five editor calls are new in the final
run. `edited_adjudicated` joins saved verdicts onto surviving finding IDs; absent means not
checked. It does not represent a fresh production-order adjudicator run, and its cost retains
all historical adjudicator calls rather than estimating savings from the newly freed slots.

| Arm | Recall | Precision (flawed videos) | Clean-control findings | Cumulative token cost |
|---|---:|---:|---:|---:|
| baseline (reused) | 19/20 (95%) | 19/20 (95%) | 3 | $0.1223 |
| rubric (reused) | 14/20 (70%) | 14/16 (88%) | 1 | $0.1474 |
| reviewers (reused) | 20/20 (100%) | 20/65 (31%) | 6 | $1.1437 |
| adjudicated (reused) | 20/20 (100%) | 20/60 (33%) | 5 | $1.3923 |
| edited | 20/20 (100%) | 20/27 (74%) | 4 | $1.1990 |
| edited_adjudicated (saved verdicts) | 20/20 (100%) | 20/26 (77%) | 4 | $1.4475 |

The editor kept 31 issue findings, merged 35 and dropped 5 across all five videos; strengths
remain unedited and are excluded by the original scorer. No planted issue was lost under the
pre-registered matcher, including the medium+ variant. Recall's 95% interval is 84–100%;
precision's intervals and paired results are in the result files. The clean-control goal
of <=2 was **missed**: four findings remain. The final pass retained the egg-storage objection,
lowered critical → high, and labelled it verified based on narrower hard-cooked guidance.
This remains a disputed/known false-positive concern from the audit: Search alone did not
resolve scope correctly. The minor egg-age ordering note also survived. Do not claim factual
verification is solved or that the editor matches the single-prompt baseline's precision.
The repo-star CTA complaint was dropped. The valid unplanted Python return-value finding was
kept by the editor, then removed by its joined historical adjudicator rejection.

**Development spend: exactly 15 live calls**, each run hard-capped with `--max-calls 5`:

| Dev run | New calls | New token estimate | Notes |
|---|---:|---:|---|
| editor-tune1 | 5 | $0.264067 | Default model reasoning; one truncated-JSON batch left unedited. |
| editor-tune2 | 5 | $0.058736 | Low reasoning; one batch with redundant unchanged severity fields left unedited. |
| editor-v1-dev (frozen) | 5 | $0.055214 | Zero editor errors; unchanged severity fields normalize to no adjustment. |
| Total | 15 | $0.378017 | 30 Search queries; charges not included. |

The two intermediate tuning outputs remain local, uncommitted. The first had 20/20 recall,
20/38 precision (20/36 with joined adjudication), clean=3. The second had 20/20 recall,
20/39 precision (20/37 with joined adjudication), clean=3. They are repeated observations of
the same dev videos, not independent samples. At $14/1,000 queries, all 30 queries would add
$0.42 if billable beyond the shared free allowance; no invoice total is asserted. Final
results report marginal editor tokens separately from reused historical arm costs.

Reproduce the frozen procedure from `backend/` with a new run ID (paid; bounded):

```bash
uv run python scripts/editorial_eval.py run \
  --root ../evals/editorial \
  --reuse-raw ../evals/results/editorial-2026-10-14-flash38.raw.json \
  --arms edited,edited_adjudicated --model gemini-3.8-flash \
  --input-price 0.75 --output-price 3.75 --max-calls 5 \
  --run-id YOUR-NEW-RUN-ID --execute
# Zero-call replay, with the same root:
uv run python scripts/editorial_score.py \
  ../evals/results/editorial-2026-10-14-editor-v1-dev.raw.json --root ../evals/editorial
```

`--root` selects labels, transcripts, media, scripts and matching rule for run/replay in both
scripts. Pre-registration checks use paths under that root, refuse uncommitted inputs, record
all input hashes for new runs, and reject replay/reuse when recorded inputs or rules differ.
Each root must be committed inside the current worktree. Existing raw files without whole-input
hashes can validate labels/matching only. The editor prompt receives creator context, transcript
and findings, never labels. Production persistence/retries and the review UI were linted,
type-checked and built, but not exercised against live Firestore or in an authenticated browser.
