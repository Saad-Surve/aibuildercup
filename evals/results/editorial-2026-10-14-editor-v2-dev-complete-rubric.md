Run `2026-10-14-editor-v2-dev-complete-rubric` - model `gemini-3.8-flash`, labels at commit `2e1357166373beb3d44765c7990311cba4f74f7d`.

Rubric recovery from `2026-10-14-editor-v2-dev-rubric-recovery` replaces index-fund-mistakes; historical failed calls/costs retained.

Reuses reviewer findings and adjudicator verdicts from `2026-10-14-flash38`. Only editor calls are new (5 calls, $0.0771 token estimate).
Adjudicated reuse joins saved verdicts only; absent verdicts mean not checked. Arm costs retain the historic full adjudicator spend; Search is unpriced.

| Arm | Recall (95% CI) | Recall, severity ≥ medium | Recall, time only | Precision | Start error, median | Clean-control findings (per min) |
|---|---:|---:|---:|---:|---:|---:|
| baseline | 19/20 95% (76-99) | 19/20 95% | 20/20 100% | 19/20 95% | 0.0 s | 3 (1.49) |
| rubric | 19/20 95% (76-99) | 19/20 95% | 20/20 100% | 19/21 90% | 0.0 s | 1 (0.5) |
| reviewers | 20/20 100% (84-100) | 20/20 100% | 20/20 100% | 20/65 31% | 0.0 s | 6 (2.99) |
| adjudicated | 20/20 100% (84-100) | 20/20 100% | 20/20 100% | 20/60 33% | 0.0 s | 5 (2.49) |
| ensemble_edited | 19/20 95% (76-99) | 19/20 95% | 20/20 100% | 19/25 76% | 0.0 s | 4 (1.99) |

Recall by category (headline matching):

| Category | baseline | rubric | reviewers | adjudicated | ensemble_edited |
|---|---:|---:|---:|---:|---:|
| broken_promise | 2/2 | 2/2 | 2/2 | 2/2 | 2/2 |
| factual_error | 2/2 | 2/2 | 2/2 | 2/2 | 2/2 |
| jargon | 2/2 | 2/2 | 2/2 | 2/2 | 2/2 |
| locale_assumption | 2/2 | 2/2 | 2/2 | 2/2 | 2/2 |
| missing_cta | 1/1 | 1/1 | 1/1 | 1/1 | 1/1 |
| pacing_drag | 1/2 | 1/2 | 2/2 | 2/2 | 1/2 |
| safety | 2/2 | 2/2 | 2/2 | 2/2 | 2/2 |
| tangent | 2/2 | 2/2 | 2/2 | 2/2 | 2/2 |
| tone_mismatch | 1/1 | 1/1 | 1/1 | 1/1 | 1/1 |
| unsupported_claim | 2/2 | 2/2 | 2/2 | 2/2 | 2/2 |
| weak_hook | 2/2 | 2/2 | 2/2 | 2/2 | 2/2 |

Cost and calls (token prices $0.75/M in, $3.75/M out; Search queries are counted, not priced):

| Arm | Model requests | Input tokens | Output tokens | Estimated USD | USD per video | USD per matched issue | Failed calls |
|---|---:|---:|---:|---:|---:|---:|---:|
| baseline | 5 | 79,230 | 16,758 | $0.1223 | $0.0245 | $0.0064 | 0 |
| rubric | 6 | 94,975 | 28,019 | $0.1763 | $0.0353 | $0.0093 | 2 |
| reviewers | 60 | 685,055 | 167,987 | $1.1437 | $0.2287 | $0.0572 | 0 |
| adjudicated | 108 | 831,421 | 205,000 | $1.3923 | $0.2785 | $0.0696 | 0 |
| ensemble_edited | 71 | 818,080 | 208,961 | $1.3972 | $0.2794 | $0.0735 | 2 |

Gold issues found, paired by issue (headline matching):

| Pair | Both | Only first | Only second | Neither |
|---|---:|---:|---:|---:|
| baseline vs rubric | 19 | 0 | 0 | 1 |
| baseline vs reviewers | 19 | 0 | 1 | 0 |
| baseline vs adjudicated | 19 | 0 | 1 | 0 |
| baseline vs ensemble_edited | 19 | 0 | 0 | 1 |
| rubric vs reviewers | 19 | 0 | 1 | 0 |
| rubric vs adjudicated | 19 | 0 | 1 | 0 |
| rubric vs ensemble_edited | 19 | 0 | 0 | 1 |
| reviewers vs adjudicated | 20 | 0 | 0 | 0 |
| reviewers vs ensemble_edited | 19 | 1 | 0 | 0 |
| adjudicated vs ensemble_edited | 19 | 1 | 0 | 0 |
