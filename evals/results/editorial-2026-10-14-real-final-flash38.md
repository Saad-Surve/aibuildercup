Run `2026-10-14-real-final-flash38` - model `gemini-3.8-flash`, labels at commit `6f1f23f7f78c4e3a09c0f85432fe2ca4d258793d`.

| Arm | Recall (95% CI) | Recall, severity ≥ medium | Recall, time only | Precision | Start error, median | Clean-control findings (per min) |
|---|---:|---:|---:|---:|---:|---:|
| baseline | 3/5 60% (23-88) | 2/5 40% | 3/5 60% | n/a (partial gold) | 0.0 s | 0 (None) |
| rubric | 2/5 40% (12-77) | 2/5 40% | 2/5 40% | n/a (partial gold) | 0.0 s | 0 (None) |
| reviewers | 2/5 40% (12-77) | 2/5 40% | 3/5 60% | n/a (partial gold) | 0.0 s | 0 (None) |
| edited | 2/5 40% (12-77) | 2/5 40% | 3/5 60% | n/a (partial gold) | 0.0 s | 0 (None) |
| ensemble_edited | 3/5 60% (23-88) | 3/5 60% | 4/5 80% | n/a (partial gold) | 0.0 s | 0 (None) |

Recall by category (headline matching):

| Category | baseline | rubric | reviewers | edited | ensemble_edited |
|---|---:|---:|---:|---:|---:|
| factual_error | 3/5 | 2/5 | 2/5 | 2/5 | 3/5 |

Cost and calls (token prices $0.75/M in, $3.75/M out; Search queries are counted, not priced):

| Arm | Model requests | Input tokens | Output tokens | Estimated USD | USD per video | USD per matched issue | Failed calls |
|---|---:|---:|---:|---:|---:|---:|---:|
| baseline | 4 | 236,741 | 14,540 | $0.2321 | $0.0580 | $0.0774 | 0 |
| rubric | 4 | 190,783 | 14,371 | $0.1970 | $0.0492 | $0.0985 | 2 |
| reviewers | 50 | 732,907 | 142,142 | $1.0827 | $0.2707 | $0.5414 | 0 |
| edited | 55 | 786,152 | 172,344 | $1.2359 | $0.3090 | $0.6180 | 0 |
| ensemble_edited | 59 | 978,702 | 192,676 | $1.4566 | $0.3641 | $0.4855 | 2 |

Gold issues found, paired by issue (headline matching):

| Pair | Both | Only first | Only second | Neither |
|---|---:|---:|---:|---:|
| baseline vs rubric | 1 | 2 | 1 | 1 |
| baseline vs reviewers | 2 | 1 | 0 | 2 |
| baseline vs edited | 2 | 1 | 0 | 2 |
| baseline vs ensemble_edited | 2 | 1 | 1 | 1 |
| rubric vs reviewers | 1 | 1 | 1 | 2 |
| rubric vs edited | 1 | 1 | 1 | 2 |
| rubric vs ensemble_edited | 2 | 0 | 1 | 2 |
| reviewers vs edited | 2 | 0 | 0 | 3 |
| reviewers vs ensemble_edited | 2 | 0 | 1 | 2 |
| edited vs ensemble_edited | 2 | 0 | 1 | 2 |
