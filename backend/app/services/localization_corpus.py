"""Global localization corpus: glossary term pairs and the hand-curated trap list.

This is the piece that makes translation better than a raw machine-translate call, as
described in `docs/technical-design/localization-corpus.md`. It holds two things per
source→target pair:

- **Glossary terms** the translation must use verbatim (brands, product terms, the
  creator's own vocabulary).
- **Traps**: idioms, false friends, code-mixing, units, dates and honorifics that generic
  machine translation reliably gets wrong, with the recommended handling.

The MVP bundle ships as JSON inside the backend image, so Cloud Run does not need the
corpus bucket to exist. The design's GCS path
(`corpus/global/{src}-{tgt}/v{n}.tsv`) and the BigQuery tables remain a workstream C
follow-up; see `corpus/README.md`. Nothing here touches an SDK — it is pure data.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Final

from app.services.dubbing import base_code

logger = logging.getLogger(__name__)

#: Version recorded on a localization so a result is reproducible.
CORPUS_VERSION: Final = 1

_CORPUS_FILE: Final = (
    Path(__file__).resolve().parent.parent / "assets" / "corpus" / "global.json"
)

#: Traps under this key apply to every language pair (for example "keep brands in Latin").
_UNIVERSAL: Final = "*"


@dataclass(frozen=True)
class GlossaryTerm:
    source: str
    target: str


@dataclass(frozen=True)
class Trap:
    category: str
    source: str
    recommended: str
    notes: str = ""


@dataclass(frozen=True)
class Corpus:
    version: int
    glossary: tuple[GlossaryTerm, ...]
    traps: tuple[Trap, ...]

    @property
    def is_empty(self) -> bool:
        return not self.glossary and not self.traps


@lru_cache(maxsize=1)
def _raw() -> dict[str, Any]:
    """Load and memoise the bundled corpus. A missing file degrades to an empty corpus."""
    try:
        data = json.loads(_CORPUS_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        logger.warning("localization corpus: could not read %s", _CORPUS_FILE, exc_info=True)
        return {}
    return data if isinstance(data, dict) else {}


def corpus_version() -> int:
    data = _raw()
    try:
        return int(data.get("version", CORPUS_VERSION))
    except (TypeError, ValueError):
        return CORPUS_VERSION


def pair_key(source_language: str | None, target_language: str | None) -> str:
    return f"{base_code(source_language)}-{base_code(target_language)}"


def _terms(raw: dict[str, Any], key: str) -> tuple[GlossaryTerm, ...]:
    items = raw.get(key)
    if not isinstance(items, list):
        return ()
    terms: list[GlossaryTerm] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        source = str(item.get("source") or "").strip()
        target = str(item.get("target") or "").strip()
        if source and target:
            terms.append(GlossaryTerm(source=source, target=target))
    return tuple(terms)


def _traps(raw: dict[str, Any], key: str) -> tuple[Trap, ...]:
    items = raw.get(key)
    if not isinstance(items, list):
        return ()
    traps: list[Trap] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        source = str(item.get("source") or "").strip()
        recommended = str(item.get("recommended") or "").strip()
        if source and recommended:
            traps.append(
                Trap(
                    category=str(item.get("category") or "general").strip() or "general",
                    source=source,
                    recommended=recommended,
                    notes=str(item.get("notes") or "").strip(),
                )
            )
    return tuple(traps)


def corpus_for(
    source_language: str | None, target_language: str | None
) -> Corpus:
    """Return the glossary + traps that apply to this language pair."""
    data = _raw()
    glossaries = data.get("glossaries")
    traps = data.get("traps")
    key = pair_key(source_language, target_language)
    glossary = _terms(glossaries, key) if isinstance(glossaries, dict) else ()
    scoped = _traps(traps, key) if isinstance(traps, dict) else ()
    universal = _traps(traps, _UNIVERSAL) if isinstance(traps, dict) else ()
    return Corpus(
        version=corpus_version(),
        glossary=glossary,
        traps=(*scoped, *universal),
    )


def available_pairs() -> list[dict[str, str]]:
    """Language pairs the bundled corpus covers, for `GET /glossaries`."""
    data = _raw()
    keys: set[str] = set()
    for section in ("glossaries", "traps"):
        values = data.get(section)
        if isinstance(values, dict):
            keys.update(str(key) for key in values)
    keys.discard(_UNIVERSAL)

    pairs: list[dict[str, str]] = []
    for key in sorted(keys):
        source, _, target = key.partition("-")
        if source and target:
            pairs.append({"sourceLanguage": source, "targetLanguage": target})
    return pairs


__all__ = [
    "CORPUS_VERSION",
    "Corpus",
    "GlossaryTerm",
    "Trap",
    "available_pairs",
    "corpus_for",
    "corpus_version",
    "pair_key",
]
