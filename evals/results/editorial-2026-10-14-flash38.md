Run `2026-10-14-flash38` - model `gemini-3.8-flash`, labels at commit `2e1357166373beb3d44765c7990311cba4f74f7d`.

| Arm | Recall (95% CI) | Recall, severity ≥ medium | Recall, time only | Precision | Start error, median | Clean-control findings (per min) |
|---|---:|---:|---:|---:|---:|---:|
| baseline | 19/20 95% (76-99) | 19/20 95% | 20/20 100% | 19/20 95% | 0.0 s | 3 (1.49) |
| rubric | 14/20 70% (48-86) | 14/20 70% | 15/20 75% | 14/16 88% | 0.0 s | 1 (0.5) |
| reviewers | 20/20 100% (84-100) | 20/20 100% | 20/20 100% | 20/65 31% | 0.0 s | 6 (2.99) |
| adjudicated | 20/20 100% (84-100) | 20/20 100% | 20/20 100% | 20/60 33% | 0.0 s | 5 (2.49) |

Recall by category (headline matching):

| Category | baseline | rubric | reviewers | adjudicated |
|---|---:|---:|---:|---:|
| broken_promise | 2/2 | 1/2 | 2/2 | 2/2 |
| factual_error | 2/2 | 2/2 | 2/2 | 2/2 |
| jargon | 2/2 | 2/2 | 2/2 | 2/2 |
| locale_assumption | 2/2 | 1/2 | 2/2 | 2/2 |
| missing_cta | 1/1 | 1/1 | 1/1 | 1/1 |
| pacing_drag | 1/2 | 1/2 | 2/2 | 2/2 |
| safety | 2/2 | 1/2 | 2/2 | 2/2 |
| tangent | 2/2 | 2/2 | 2/2 | 2/2 |
| tone_mismatch | 1/1 | 0/1 | 1/1 | 1/1 |
| unsupported_claim | 2/2 | 1/2 | 2/2 | 2/2 |
| weak_hook | 2/2 | 2/2 | 2/2 | 2/2 |

Cost and calls (token prices $0.75/M in, $3.75/M out; Search queries are counted, not priced):

| Arm | Model requests | Input tokens | Output tokens | Estimated USD | USD per matched issue | Failed calls |
|---|---:|---:|---:|---:|---:|---:|
| baseline | 5 | 79,230 | 16,758 | $0.1223 | $0.0064 | 0 |
| rubric | 5 | 77,182 | 23,861 | $0.1474 | $0.0105 | 2 |
| reviewers | 60 | 685,055 | 167,987 | $1.1437 | $0.0572 | 0 |
| adjudicated | 108 | 831,421 | 205,000 | $1.3923 | $0.0696 | 0 |

Gold issues found, paired by issue (headline matching):

| Pair | Both | Only first | Only second | Neither |
|---|---:|---:|---:|---:|
| baseline vs rubric | 14 | 5 | 0 | 1 |
| baseline vs reviewers | 19 | 0 | 1 | 0 |
| baseline vs adjudicated | 19 | 0 | 1 | 0 |
| rubric vs reviewers | 14 | 0 | 6 | 0 |
| rubric vs adjudicated | 14 | 0 | 6 | 0 |
| reviewers vs adjudicated | 20 | 0 | 0 | 0 |
