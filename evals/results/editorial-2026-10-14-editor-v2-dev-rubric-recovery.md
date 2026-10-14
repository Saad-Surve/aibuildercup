Run `2026-10-14-editor-v2-dev-rubric-recovery` - model `gemini-3.8-flash`, labels at commit `2e1357166373beb3d44765c7990311cba4f74f7d`.

| Arm | Recall (95% CI) | Recall, severity ≥ medium | Recall, time only | Precision | Start error, median | Clean-control findings (per min) |
|---|---:|---:|---:|---:|---:|---:|
| rubric | 5/5 100% (57-100) | 5/5 100% | 5/5 100% | 5/5 100% | 0.0 s | 0 (None) |

Recall by category (headline matching):

| Category | rubric |
|---|---:|
| broken_promise | 1/1 |
| locale_assumption | 1/1 |
| safety | 1/1 |
| tone_mismatch | 1/1 |
| unsupported_claim | 1/1 |

Cost and calls (token prices $0.75/M in, $3.75/M out; Search queries are counted, not priced):

| Arm | Model requests | Input tokens | Output tokens | Estimated USD | USD per video | USD per matched issue | Failed calls |
|---|---:|---:|---:|---:|---:|---:|---:|
| rubric | 1 | 17,793 | 4,158 | $0.0289 | $0.0289 | $0.0058 | 0 |
