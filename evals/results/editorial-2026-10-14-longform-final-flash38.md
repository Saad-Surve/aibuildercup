Run `2026-10-14-longform-final-flash38` - model `gemini-3.8-flash`, labels at commit `9d48bf514af7fb1d1823c2f2266ff869752f4a80`.

| Arm | Recall (95% CI) | Recall, severity ≥ medium | Recall, time only | Precision | Start error, median | Clean-control findings (per min) |
|---|---:|---:|---:|---:|---:|---:|
| baseline | 27/32 84% (68-93) | 27/32 84% | 27/32 84% | 27/27 100% | 0.0 s | 2 (0.24) |
| rubric | 28/32 88% (72-95) | 28/32 88% | 28/32 88% | 28/29 97% | 0.0 s | 5 (0.6) |
| reviewers | 31/32 97% (84-99) | 31/32 97% | 31/32 97% | 31/75 41% | 0.0 s | 14 (1.68) |
| edited | 29/32 91% (76-97) | 29/32 91% | 30/32 94% | 29/33 88% | 0.0 s | 4 (0.48) |
| ensemble_edited | 31/32 97% (84-99) | 31/32 97% | 31/32 97% | 31/34 91% | 0.0 s | 6 (0.72) |

Recall by category (headline matching):

| Category | baseline | rubric | reviewers | edited | ensemble_edited |
|---|---:|---:|---:|---:|---:|
| broken_promise | 4/4 | 4/4 | 4/4 | 4/4 | 4/4 |
| factual_error | 4/4 | 4/4 | 4/4 | 4/4 | 4/4 |
| jargon | 3/3 | 3/3 | 3/3 | 2/3 | 3/3 |
| locale_assumption | 1/2 | 2/2 | 2/2 | 1/2 | 2/2 |
| missing_cta | 2/2 | 2/2 | 2/2 | 2/2 | 2/2 |
| pacing_drag | 1/3 | 2/3 | 3/3 | 3/3 | 3/3 |
| safety | 2/2 | 2/2 | 2/2 | 2/2 | 2/2 |
| tangent | 3/4 | 3/4 | 3/4 | 3/4 | 3/4 |
| tone_mismatch | 2/2 | 2/2 | 2/2 | 2/2 | 2/2 |
| unsupported_claim | 4/4 | 2/4 | 4/4 | 4/4 | 4/4 |
| weak_hook | 1/2 | 2/2 | 2/2 | 2/2 | 2/2 |

Cost and calls (token prices $0.75/M in, $3.75/M out; Search queries are counted, not priced):

| Arm | Model requests | Input tokens | Output tokens | Estimated USD | USD per video | USD per matched issue | Failed calls |
|---|---:|---:|---:|---:|---:|---:|---:|
| baseline | 5 | 328,087 | 26,409 | $0.3451 | $0.0690 | $0.0128 | 0 |
| rubric | 5 | 343,832 | 37,960 | $0.4002 | $0.0800 | $0.0143 | 0 |
| reviewers | 53 | 857,513 | 197,075 | $1.3822 | $0.2764 | $0.0446 | 0 |
| edited | 62 | 971,771 | 261,485 | $1.7094 | $0.3419 | $0.0589 | 0 |
| ensemble_edited | 67 | 1,324,379 | 315,843 | $2.1777 | $0.4355 | $0.0702 | 0 |

Gold issues found, paired by issue (headline matching):

| Pair | Both | Only first | Only second | Neither |
|---|---:|---:|---:|---:|
| baseline vs rubric | 25 | 2 | 3 | 2 |
| baseline vs reviewers | 27 | 0 | 4 | 1 |
| baseline vs edited | 26 | 1 | 3 | 2 |
| baseline vs ensemble_edited | 27 | 0 | 4 | 1 |
| rubric vs reviewers | 28 | 0 | 3 | 1 |
| rubric vs edited | 26 | 2 | 3 | 1 |
| rubric vs ensemble_edited | 28 | 0 | 3 | 1 |
| reviewers vs edited | 29 | 2 | 0 | 1 |
| reviewers vs ensemble_edited | 31 | 0 | 0 | 1 |
| edited vs ensemble_edited | 29 | 0 | 2 | 1 |
