"""Repair Markdown that a model returned with its escapes left in.

Gemini sometimes answers a `response_schema` string field with the newlines and
quotes JSON-escaped (``\\n``, ``\\"``) even though the outer JSON object was
already decoded by the provider. The stored document is then a single physical
line, so anything that expects lines — the persona renderer, or the reviewer
prompt that embeds the persona — sees one giant paragraph.

`normalize_markdown` repairs that shape and leaves ordinary Markdown untouched.
It is deliberately conservative: it only acts when the text has no real newline
but does contain a literal ``\\n`` escape, and it only rewrites the text when it
decodes as a well-formed JSON string body. Anything ambiguous is returned as-is.
"""

import json


def normalize_markdown(markdown: str) -> str:
    """Return ``markdown`` with model-escaped newlines/quotes decoded."""
    if not markdown or "\n" in markdown or "\\n" not in markdown:
        return markdown
    # The whole document is one JSON-escaped line. Decode it as a JSON string
    # body so newlines, quotes, tabs, and unicode escapes land exactly as the
    # model intended. If it is not a valid JSON string (for example a code span
    # that legitimately contains a literal backslash-n), leave it alone.
    try:
        decoded = json.loads(f'"{markdown}"')
    except (ValueError, TypeError):
        return markdown
    return decoded if isinstance(decoded, str) else markdown
