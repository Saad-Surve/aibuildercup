# Evaluation results index

One entry per run. All editorial runs used model `gemini-3.8-flash` and were made on 14 October 2026.
Terminology (arms, matching rule, recall, precision) is in [../editorial/README.md](../editorial/README.md);
the retrieval benchmark is in [../README.md](../README.md). Prefix every run id with `editorial-` for file names.

## File types

| Suffix | Contents |
|---|---|
| `.md` | Human-readable report: tables per arm. |
| `.json` | Scored results: metrics, labels commit and hashes, prompt versions, cost, model calls. |
| `.raw.json` | Every model response and normalised finding. Re-score offline with `editorial_eval.py replay` (no model calls). |
| `.audit.md` / `.audit.json` | Model-judged classification of unmatched findings (not human-verified). |
| `.evidence/` | Frames and clips the reviewers requested, per video. |

## Pre-registered evaluations (run once)

| Run id | Set, labels commit | Arms | Purpose |
|---|---|---|---|
| `2026-10-14-heldout-flash38` | HELD-OUT (`evals/editorial-heldout`, 6 videos, 22 planted issues), `6df94ce` | baseline, rubric, reviewers, adjudicated, edited, edited_adjudicated | Pre-registered evaluation (run once) of the editor frozen on the dev set. Files: `.md`, `.json`, `.raw.json`, `.evidence/`. |
| `2026-10-14-longform-final-flash38` | LONG-FORM (`evals/editorial-longform`, 5 long videos, 32 planted issues), `9d48bf5` | baseline, rubric, reviewers, edited, ensemble_edited | Pre-registered evaluation (run once) on long videos with subtler flaws. Files: `.md`, `.json`, `.raw.json`. |
| `2026-10-14-real-final-flash38` | REAL (`evals/editorial-real`, 4 CC BY creator videos, 5 creator-published corrections, recall only), `6f1f23f` | baseline, rubric, reviewers, edited, ensemble_edited | Pre-registered evaluation (run once). Resonance 3/5 known errors, one prompt 3/5; the rubric call failed on one video (2 failed calls). |

Each of these may not be re-run or tuned against. Do not read the partial real raw file as a result.

## Dev baseline (flash38) and its audit

| Run id | Set, labels commit | Arms | Purpose |
|---|---|---|---|
| `2026-10-14-flash38` | DEV (`evals/editorial`, 5 videos, 20 planted issues, 1 clean control), `2e13571` | baseline, rubric, reviewers, adjudicated | First live run, 118 calls. It is the source of the reviewer and adjudicator output that every later dev run reuses. Files: `.md`, `.json`, `.raw.json`, `.evidence/`. |
| `2026-10-14-flash38.audit` | DEV, same run | baseline, reviewers, adjudicated (100 unmatched findings) | Classifies each unmatched finding as duplicate, valid_unplanted, nitpick or spurious. One model's judgment, not human-verified. Files: `.audit.md`, `.audit.json`. |

## Dev tuning runs: post-hoc tuning (dev set)

All use DEV, labels `2e13571`, and reuse saved raw output through `--reuse-raw`. Only the editor stage (and the
named rubric calls) is new. They are repeated looks at known labels, not confirmatory evidence.

| Run id | Arms | Purpose |
|---|---|---|
| `2026-10-14-editor-tune1` | baseline, rubric, reviewers, adjudicated, edited, edited_adjudicated | Post-hoc tuning (dev set). Editor v1 attempt 1, default reasoning, 5 new calls. Superseded. |
| `2026-10-14-editor-tune2` | same six | Post-hoc tuning (dev set). Editor v1 attempt 2, low reasoning, 5 new calls. Superseded. |
| `2026-10-14-editor-v1-dev` | same six | Post-hoc tuning (dev set). Frozen editor v1 pass (`editor-v1`), 5 new calls, reuses flash38. |
| `2026-10-14-editor-v2-dev-rubric-recovery` | rubric (1 video, `index-fund-mistakes`) | Input, not a result. Re-runs one failed rubric call so the complete-rubric run can reuse it. |
| `2026-10-14-editor-v2-dev-complete-rubric` | baseline, rubric, reviewers, adjudicated, ensemble_edited | Input, not a result. Completes the rubric arm and adds the ensemble arm; reused by v6. |
| `2026-10-14-editor-v2-dev-v6` | baseline, rubric, reviewers, adjudicated, edited, ensemble_edited | Post-hoc tuning (dev set). Final frozen dev run (`editor-v6`, medium reasoning), 10 new editor calls. Its editor is the one applied to the pre-registered sets. |

## 11 October retrieval benchmark and cost scenario

Not editorial runs. Described in [../README.md](../README.md).

| File | Contents |
|---|---|
| `2026-10-11.json` | First live retrieval and runtime benchmark: creator retrieval (20 cases), component latencies, media metadata, web payload sizes. |
| `2026-10-11-replay.json` | Offline replay of the same benchmark with zero new model calls; reproduces the retrieval metrics and adds implementation hashes. |
| `cost-scenario.json` | Illustrative component cost estimate for one scenario (five-minute video, nine reviewers, one draft, four thumbnails, one dub). Not an invoice. |
