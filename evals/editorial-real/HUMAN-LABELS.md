# Later human labels

Fill this in for two or three of the videos below, before reading model findings. These are
independent creator/editor judgments, separate from the creator-published correction answer key.
Keep this template unfilled in the initial pre-registration commit. Add completed annotations
later in a separate commit with its date in the commit message and annotation header; disclose
whether the annotator had already seen any model output. Do not call these exhaustive gold.

Annotator: ______  Date (YYYY-MM-DD): ______  Model output seen beforehand: yes / no

| Video | Timestamp range (mm:ss.mmm–mm:ss.mmm) | Category | Description / evidence | Severity |
|---|---|---|---|---|
| `BBvze0lGcZg` — Book publishing | ______ | ______ | ______ | ______ |
| `FqYg-gjCrPw` — Auto tune and pitch correction | ______ | ______ | ______ | ______ |
| `mMZYKxgc9TE` — Ukraine and Russia | ______ | ______ | ______ | ______ |

Duplicate a row for each distinct issue. Use the actual speech/footage range, quote what you
observed, and explain the viewer consequence. Describe a useful edit if possible. When one issue
repeats, list its other ranges in the description rather than treating it as multiple issues.

Categories, exactly as in [matching.json](matching.json): `weak_hook`, `unsupported_claim`,
`factual_error`, `jargon`, `tangent`, `pacing_drag`, `missing_cta`, `safety`, `broken_promise`,
`tone_mismatch`, `locale_assumption`.

Severity: `low`, `medium`, `high`, `critical`. Use `none` only for a separately identified
strength; strengths are not gold issues. Leave disputed judgments marked as disputed until a
human resolves them. Leave `partialGold: true` when converting annotations to label JSON.

Henry (`JhVJMO0wgTE`) is intentionally omitted: sensitive patient story, evaluation only,
never on screen or in a public demo.
