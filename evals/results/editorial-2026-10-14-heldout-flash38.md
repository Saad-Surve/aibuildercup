Run `2026-10-14-heldout-flash38` - model `gemini-3.8-flash`, labels at commit `6df94ce1bf1bf4e80d5dad11afdad6059de1f04f`.

| Arm | Recall (95% CI) | Recall, severity ≥ medium | Recall, time only | Precision | Start error, median | Clean-control findings (per min) |
|---|---:|---:|---:|---:|---:|---:|
| baseline | 18/22 82% (62-93) | 17/22 77% | 18/22 82% | 18/18 100% | 0.0 s | 3 (0.73) |
| rubric | 20/22 91% (72-98) | 20/22 91% | 21/22 96% | 20/21 95% | 0.0 s | 2 (0.49) |
| reviewers | 22/22 100% (85-100) | 22/22 100% | 22/22 100% | 22/65 34% | 0.0 s | 5 (1.21) |
| adjudicated | 22/22 100% (85-100) | 22/22 100% | 22/22 100% | 22/60 37% | 0.0 s | 3 (0.73) |
| edited | 21/22 96% (78-99) | 19/22 86% | 22/22 100% | 21/27 78% | 0.0 s | 1 (0.24) |
| edited_adjudicated | 20/22 91% (72-98) | 18/22 82% | 21/22 96% | 20/26 77% | 0.0 s | 1 (0.24) |

Recall by category (headline matching):

| Category | baseline | rubric | reviewers | adjudicated | edited | edited_adjudicated |
|---|---:|---:|---:|---:|---:|---:|
| broken_promise | 2/2 | 2/2 | 2/2 | 2/2 | 1/2 | 0/2 |
| factual_error | 2/2 | 2/2 | 2/2 | 2/2 | 2/2 | 2/2 |
| jargon | 2/2 | 2/2 | 2/2 | 2/2 | 2/2 | 2/2 |
| locale_assumption | 2/2 | 2/2 | 2/2 | 2/2 | 2/2 | 2/2 |
| missing_cta | 2/2 | 2/2 | 2/2 | 2/2 | 2/2 | 2/2 |
| pacing_drag | 2/2 | 1/2 | 2/2 | 2/2 | 2/2 | 2/2 |
| safety | 2/2 | 2/2 | 2/2 | 2/2 | 2/2 | 2/2 |
| tangent | 0/2 | 2/2 | 2/2 | 2/2 | 2/2 | 2/2 |
| tone_mismatch | 2/2 | 2/2 | 2/2 | 2/2 | 2/2 | 2/2 |
| unsupported_claim | 0/2 | 1/2 | 2/2 | 2/2 | 2/2 | 2/2 |
| weak_hook | 2/2 | 2/2 | 2/2 | 2/2 | 2/2 | 2/2 |

Cost and calls (token prices $0.75/M in, $3.75/M out; Search queries are counted, not priced):

| Arm | Model requests | Input tokens | Output tokens | Estimated USD | USD per matched issue | Failed calls |
|---|---:|---:|---:|---:|---:|---:|
| baseline | 6 | 126,888 | 16,360 | $0.1565 | $0.0087 | 0 |
| rubric | 6 | 145,782 | 26,297 | $0.2079 | $0.0104 | 0 |
| reviewers | 73 | 881,899 | 205,800 | $1.4332 | $0.0651 | 0 |
| adjudicated | 116 | 1,010,646 | 239,420 | $1.6558 | $0.0753 | 0 |
| edited | 79 | 919,329 | 214,730 | $1.4947 | $0.0712 | 0 |
| edited_adjudicated | 91 | 958,574 | 223,598 | $1.5574 | $0.0779 | 0 |

Gold issues found, paired by issue (headline matching):

| Pair | Both | Only first | Only second | Neither |
|---|---:|---:|---:|---:|
| baseline vs rubric | 17 | 1 | 3 | 1 |
| baseline vs reviewers | 18 | 0 | 4 | 0 |
| baseline vs adjudicated | 18 | 0 | 4 | 0 |
| baseline vs edited | 17 | 1 | 4 | 0 |
| baseline vs edited_adjudicated | 16 | 2 | 4 | 0 |
| rubric vs reviewers | 20 | 0 | 2 | 0 |
| rubric vs adjudicated | 20 | 0 | 2 | 0 |
| rubric vs edited | 19 | 1 | 2 | 0 |
| rubric vs edited_adjudicated | 18 | 2 | 2 | 0 |
| reviewers vs adjudicated | 22 | 0 | 0 | 0 |
| reviewers vs edited | 21 | 1 | 0 | 0 |
| reviewers vs edited_adjudicated | 20 | 2 | 0 | 0 |
| adjudicated vs edited | 21 | 1 | 0 | 0 |
| adjudicated vs edited_adjudicated | 20 | 2 | 0 | 0 |
| edited vs edited_adjudicated | 20 | 1 | 0 | 1 |
