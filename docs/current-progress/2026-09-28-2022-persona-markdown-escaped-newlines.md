# Persona Markdown: repair model-escaped newlines (root cause)

## What I found

The renderer was not the (whole) problem. The stored `persona.md` for an
LLM-generated persona is a **single physical line**: Gemini answered the
`response_schema` string field `markdown` with its newlines and quotes
JSON-escaped (`\n`, `\"`) even though the provider already decoded the outer JSON
object. So `PersonaText` saw one line starting `# Creator Persona: …\n\n## Identity…`,
matched the leading `#`, and put the entire document inside one `<h2>`.

Symptoms in the raw string: literal `\n` (backslash-n) instead of breaks, and
escaped quotes such as `Global (\"Everywhere\")`.

The deterministic template fallback (`build_persona_markdown`) builds real
newlines, which is why template-only data never showed the bug — only the LLM
path.

## What I did

New `backend/app/services/markdown_repair.py` — `normalize_markdown(text)`:

- No-op unless the text has **no real newline** but **does contain a literal `\n`**.
- Then decodes it as a JSON string body (`json.loads('"' + text + '"')`), which
  restores newlines, quotes, tabs, and unicode escapes exactly as intended.
- Anything ambiguous (invalid JSON string body, e.g. a code span that legitimately
  contains `\n`) is returned unchanged — no false repairs.

Applied it at every boundary that matters:

- `persona_service._generate_markdown` — new personas are stored clean (and the
  reviewer prompt gets clean context).
- `persona_service.get` — **existing** personas are repaired on read, so the
  profile and onboarding screens are fixed without a regeneration or migration.
- `persona_service.update` — PATCHed content is repaired before it is persisted.
- `analysis_worker._load_persona` — the analysis reviewer prompt reads storage
  directly, so it is repaired there too. Normalisation now happens *before* the
  4000-char excerpt slice, which previously could cut mid-escape.

## Structural changes

Backend only, one new service module. No API contract, schema, or storage-path
changes. Existing broken objects are repaired on read; nothing needs rewriting.

## Verification

- Reproduced the bug from the user's pasted content and confirmed the repair
  turns it back into real multi-line Markdown with unescaped quotes.
- Guard checks: ordinary Markdown, a legit literal `\n` in a code span, and a
  regex-like `\d+\s+` are all returned unchanged.
- `uv run ruff check .` clean; `uv run mypy app` clean (76 files).
- Backend runs with `uvicorn --reload`, so the running dev server has the fix;
  refresh the profile page to see clean Markdown.

## Not done / next step

- Uncommitted (with the earlier profile-menu + renderer work). Say so and I'll
  commit all of it together.
- Optional hardening: also normalise in the LLM provider for any future
  free-form Markdown schema field, instead of per-feature.
