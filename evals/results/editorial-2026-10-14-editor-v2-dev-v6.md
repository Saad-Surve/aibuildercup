Run `2026-10-14-editor-v2-dev-v6` - model `gemini-3.8-flash`, labels at commit `2e1357166373beb3d44765c7990311cba4f74f7d`.

Reuses reviewer findings and adjudicator verdicts from `2026-10-14-editor-v2-dev-complete-rubric`. Only editor calls are new (10 calls, $0.5240 token estimate).
Adjudicated reuse joins saved verdicts only; absent verdicts mean not checked. Arm costs retain the historic full adjudicator spend; Search is unpriced.

| Arm | Recall (95% CI) | Recall, severity ≥ medium | Recall, time only | Precision | Start error, median | Clean-control findings (per min) |
|---|---:|---:|---:|---:|---:|---:|
| baseline | 19/20 95% (76-99) | 19/20 95% | 20/20 100% | 19/20 95% | 0.0 s | 3 (1.49) |
| rubric | 19/20 95% (76-99) | 19/20 95% | 20/20 100% | 19/21 90% | 0.0 s | 1 (0.5) |
| reviewers | 20/20 100% (84-100) | 20/20 100% | 20/20 100% | 20/65 31% | 0.0 s | 6 (2.99) |
| adjudicated | 20/20 100% (84-100) | 20/20 100% | 20/20 100% | 20/60 33% | 0.0 s | 5 (2.49) |
| edited | 20/20 100% (84-100) | 20/20 100% | 20/20 100% | 20/25 80% | 0.0 s | 1 (0.5) |
| ensemble_edited | 20/20 100% (84-100) | 20/20 100% | 20/20 100% | 20/23 87% | 0.0 s | 1 (0.5) |

Recall by category (headline matching):

| Category | baseline | rubric | reviewers | adjudicated | edited | ensemble_edited |
|---|---:|---:|---:|---:|---:|---:|
| broken_promise | 2/2 | 2/2 | 2/2 | 2/2 | 2/2 | 2/2 |
| factual_error | 2/2 | 2/2 | 2/2 | 2/2 | 2/2 | 2/2 |
| jargon | 2/2 | 2/2 | 2/2 | 2/2 | 2/2 | 2/2 |
| locale_assumption | 2/2 | 2/2 | 2/2 | 2/2 | 2/2 | 2/2 |
| missing_cta | 1/1 | 1/1 | 1/1 | 1/1 | 1/1 | 1/1 |
| pacing_drag | 1/2 | 1/2 | 2/2 | 2/2 | 2/2 | 2/2 |
| safety | 2/2 | 2/2 | 2/2 | 2/2 | 2/2 | 2/2 |
| tangent | 2/2 | 2/2 | 2/2 | 2/2 | 2/2 | 2/2 |
| tone_mismatch | 1/1 | 1/1 | 1/1 | 1/1 | 1/1 | 1/1 |
| unsupported_claim | 2/2 | 2/2 | 2/2 | 2/2 | 2/2 | 2/2 |
| weak_hook | 2/2 | 2/2 | 2/2 | 2/2 | 2/2 | 2/2 |

Cost and calls (token prices $0.75/M in, $3.75/M out; Search queries are counted, not priced):

| Arm | Model requests | Input tokens | Output tokens | Estimated USD | USD per video | USD per matched issue | Failed calls |
|---|---:|---:|---:|---:|---:|---:|---:|
| baseline | 5 | 79,230 | 16,758 | $0.1223 | $0.0245 | $0.0064 | 0 |
| rubric | 6 | 94,975 | 28,019 | $0.1763 | $0.0353 | $0.0093 | 2 |
| reviewers | 60 | 685,055 | 167,987 | $1.1437 | $0.2287 | $0.0572 | 0 |
| adjudicated | 108 | 831,421 | 205,000 | $1.3923 | $0.2785 | $0.0696 | 0 |
| edited | 65 | 720,769 | 230,019 | $1.4031 | $0.2806 | $0.0702 | 0 |
| ensemble_edited | 71 | 821,125 | 258,350 | $1.5847 | $0.3169 | $0.0792 | 2 |

Gold issues found, paired by issue (headline matching):

| Pair | Both | Only first | Only second | Neither |
|---|---:|---:|---:|---:|
| baseline vs rubric | 19 | 0 | 0 | 1 |
| baseline vs reviewers | 19 | 0 | 1 | 0 |
| baseline vs adjudicated | 19 | 0 | 1 | 0 |
| baseline vs edited | 19 | 0 | 1 | 0 |
| baseline vs ensemble_edited | 19 | 0 | 1 | 0 |
| rubric vs reviewers | 19 | 0 | 1 | 0 |
| rubric vs adjudicated | 19 | 0 | 1 | 0 |
| rubric vs edited | 19 | 0 | 1 | 0 |
| rubric vs ensemble_edited | 19 | 0 | 1 | 0 |
| reviewers vs adjudicated | 20 | 0 | 0 | 0 |
| reviewers vs edited | 20 | 0 | 0 | 0 |
| reviewers vs ensemble_edited | 20 | 0 | 0 | 0 |
| adjudicated vs edited | 20 | 0 | 0 | 0 |
| adjudicated vs ensemble_edited | 20 | 0 | 0 | 0 |
| edited vs ensemble_edited | 20 | 0 | 0 | 0 |

Frozen `editor-v6` (source SHA-256 `f93a7d7b0685e4d9c15b5c6d57be84fca7cae8e9ce5a207482bdc478df71385f`), model config `analysis-v9`.

Workstream audit: **62/120 recorded live calls**, including interrupted attempts; reused historical calls are excluded. The raw JSON contains the per-run ledger and hashes before intermediate cleanup. Historical hidden retries cannot be reconstructed.

The ensemble improves recall over rubric (20/20 versus 19/20), but precision is lower (20/23, 86.96%, versus 19/21, 90.48%), clean findings tie at 1, and cost is about nine times higher. The >=88% precision target is **not met**. No overall dev win; no further tuning on these five videos.

v4 had ensemble recall 20/20, precision 20/24 (83.33%) and clean findings 3; v6 is the better frozen version. v5 only completed part of the set and had a truncated editor response; it cannot support a full-set comparison. The v5/v6 general defect threshold, reasoning change and output allowance remain in the frozen code, as disclosed in the DEV README.
