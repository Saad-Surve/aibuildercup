"""Gemini cultural-adaptation pass for localized transcripts.

Cloud Translation produces a literal draft. This pass rewrites that draft for a viewer in
the target language, constrained by the global corpus and the project glossary: it enforces
the glossary terms, applies the trap list, keeps brand names and code-mixing, localizes
units/dates/honorifics, and makes each line speakable for Text-to-Speech.

It is **best-effort**. Any failed batch keeps its raw machine translation, so a dub never
fails because the second pass did. The number of lines is guaranteed to match the input so
the caller can keep pairing lines with transcript segments.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from app.providers.base import LlmProvider
from app.services.localization_corpus import Corpus

logger = logging.getLogger(__name__)

ADAPT_PROMPT_VERSION = "localization-adapt-v1"

#: Keep one model call small enough to stay fast and cheap on a long transcript.
_DEFAULT_MAX_CHARS = 8_000
_MAX_LINES = 40

SYSTEM_PROMPT = """You are a professional audiovisual translator and localization editor.

You are given a source line and a raw machine-translation draft for each line of a video
transcript. Rewrite each draft so it reads and sounds natural to a native speaker of the
target language, while staying faithful to the source.

Rules:
- Produce exactly one line per input line, in the same order. Never split, merge, drop or
  add lines.
- Use every glossary term exactly as supplied, whenever its source term appears.
- Apply the trap list: fix idioms, false friends, units, currency, dates and honorifics as
  recommended; never translate a brand or product name, keep it in Latin script.
- Preserve intentional code-mixing and the speaker's register.
- Keep lines short and speakable: they are synthesized by Text-to-Speech and must fit the
  original time window. Do not pad or explain.
- Return only the translated lines. No commentary, no notes, no quotes."""


def adapt_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "translations": {
                "type": "array",
                "items": {"type": "string"},
            }
        },
        "required": ["translations"],
    }


def _chunks(sources: list[str], max_chars: int) -> list[list[int]]:
    """Group line indexes into batches under a char budget and line-count cap."""
    chunks: list[list[int]] = []
    current: list[int] = []
    size = 0
    for index, text in enumerate(sources):
        if current and (
            len(current) >= _MAX_LINES or size + len(text) > max_chars
        ):
            chunks.append(current)
            current = []
            size = 0
        current.append(index)
        size += len(text)
    if current:
        chunks.append(current)
    return chunks


def _corpus_payload(corpus: Corpus, target_language: str) -> dict[str, Any]:
    return {
        "target_language": target_language,
        "glossary": [
            {"source": term.source, "target": term.target}
            for term in corpus.glossary
        ],
        "traps": [
            {
                "category": trap.category,
                "source": trap.source,
                "recommended": trap.recommended,
                "notes": trap.notes,
            }
            for trap in corpus.traps
        ],
    }


async def adapt_translations(
    sources: list[str],
    drafts: list[str],
    *,
    source_language: str | None,
    target_language: str,
    corpus: Corpus,
    llm: LlmProvider,
    model: str,
    max_chars: int = _DEFAULT_MAX_CHARS,
) -> list[str]:
    """Return culturally adapted translations, one per input line.

    Best-effort: a batch that fails keeps its machine-translation draft.
    """
    if not sources:
        return []
    result = list(drafts)
    if len(result) != len(sources):
        result = list(sources)

    batches = _chunks(sources, max(1, max_chars))
    context = _corpus_payload(corpus, target_language)
    for number, batch in enumerate(batches, start=1):
        lines = [
            {
                "index": index,
                "source": sources[index],
                "draft": result[index],
            }
            for index in batch
        ]
        user = json.dumps(
            {
                "source_language": source_language,
                **context,
                "lines": lines,
            },
            ensure_ascii=False,
        )
        try:
            completion = await llm.complete_json(
                model=model,
                prompt_version=ADAPT_PROMPT_VERSION,
                system=SYSTEM_PROMPT,
                user=user,
                schema=adapt_schema(),
            )
        except Exception:  # noqa: BLE001 - adaptation must never fail a dub
            logger.exception(
                "localization adapt: batch %d/%d failed; keeping machine drafts",
                number,
                len(batches),
            )
            continue

        raw = completion.data.get("translations")
        if not isinstance(raw, list) or len(raw) != len(batch):
            logger.warning(
                "localization adapt: batch %d/%d returned %s lines, expected %d",
                number,
                len(batches),
                len(raw) if isinstance(raw, list) else "no",
                len(batch),
            )
            continue
        for offset, index in enumerate(batch):
            value = raw[offset]
            if isinstance(value, str) and value.strip():
                result[index] = value.strip()

    return result


__all__ = [
    "ADAPT_PROMPT_VERSION",
    "adapt_schema",
    "adapt_translations",
]
