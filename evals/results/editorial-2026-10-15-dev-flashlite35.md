Run `2026-10-15-dev-flashlite35` - model `gemini-3.5-flash-lite`, labels at commit `2e1357166373beb3d44765c7990311cba4f74f7d`.

| Arm | Recall (95% CI) | Recall, severity ≥ medium | Recall, time only | Precision | Start error, median | Clean-control findings (per min) |
|---|---:|---:|---:|---:|---:|---:|
| baseline | 5/20 25% (11-47) | 5/20 25% | 5/20 25% | 5/5 100% | 0.0 s | 0 (0.0) |
| rubric | 11/20 55% (34-74) | 11/20 55% | 11/20 55% | 11/11 100% | 0.0 s | 0 (0.0) |
| reviewers | 19/20 95% (76-99) | 19/20 95% | 19/20 95% | 19/46 41% | 0.0 s | 2 (1.0) |
| ensemble_edited | 17/20 85% (64-95) | 17/20 85% | 17/20 85% | 17/19 90% | 0.0 s | 0 (0.0) |

Recall by category (headline matching):

| Category | baseline | rubric | reviewers | ensemble_edited |
|---|---:|---:|---:|---:|
| broken_promise | 0/2 | 0/2 | 2/2 | 0/2 |
| factual_error | 1/2 | 1/2 | 2/2 | 2/2 |
| jargon | 1/2 | 2/2 | 2/2 | 2/2 |
| locale_assumption | 0/2 | 0/2 | 2/2 | 2/2 |
| missing_cta | 0/1 | 1/1 | 1/1 | 1/1 |
| pacing_drag | 0/2 | 0/2 | 1/2 | 1/2 |
| safety | 2/2 | 2/2 | 2/2 | 2/2 |
| tangent | 0/2 | 2/2 | 2/2 | 2/2 |
| tone_mismatch | 1/1 | 1/1 | 1/1 | 1/1 |
| unsupported_claim | 0/2 | 0/2 | 2/2 | 2/2 |
| weak_hook | 0/2 | 2/2 | 2/2 | 2/2 |

Cost and calls (token prices $0.25/M in, $1.5/M out; Search queries are counted, not priced):

| Arm | Model requests | Input tokens | Output tokens | Estimated USD | USD per video | USD per matched issue | Failed calls |
|---|---:|---:|---:|---:|---:|---:|---:|
| baseline | 5 | 45,239 | 1,268 | $0.0132 | $0.0026 | $0.0026 | 4 |
| rubric | 5 | 77,733 | 2,489 | $0.0232 | $0.0046 | $0.0021 | 2 |
| reviewers | 45 | 483,756 | 11,617 | $0.1384 | $0.0277 | $0.0073 | 0 |
| ensemble_edited | 55 | 591,603 | 22,801 | $0.1821 | $0.0364 | $0.0107 | 2 |

Gold issues found, paired by issue (headline matching):

| Pair | Both | Only first | Only second | Neither |
|---|---:|---:|---:|---:|
| baseline vs rubric | 5 | 0 | 6 | 9 |
| baseline vs reviewers | 5 | 0 | 14 | 1 |
| baseline vs ensemble_edited | 5 | 0 | 12 | 3 |
| rubric vs reviewers | 11 | 0 | 8 | 1 |
| rubric vs ensemble_edited | 11 | 0 | 6 | 3 |
| reviewers vs ensemble_edited | 17 | 2 | 0 | 1 |
