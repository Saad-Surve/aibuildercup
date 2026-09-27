"""Post-Chirp transcript cleanup and speaker inference.

Speech-to-Text is good but not perfect: it mangles proper nouns, picks the wrong
homophone, and occasionally splits or merges words. This module runs one cheap,
conservative LLM pass over the segments Chirp produced and applies *only* fixes
that look like recogniser errors. It is explicitly forbidden from rewriting,
paraphrasing, translating, or tidying the speaker's actual language.

The same pass infers speaker turns when diarization is missing or wrong, using
references in the text (names, "my co-host", interviewer questions). It can also
name the voices via a `speakerLabels` map, which the transcript carries for the UI.

Everything here is best-effort: a batch that fails is logged and its segments are
left exactly as Chirp returned them, so cleanup can never cost a transcript.
"""

import logging
from dataclasses import dataclass, field
from typing import Any

from app.providers.base import LlmProvider, LlmUsage

logger = logging.getLogger(__name__)

#: Bumped whenever the repair prompt/schema changes in a way that alters output.
REPAIR_PROMPT_VERSION = "transcript-repair-v1"

_MAX_SPEAKER_INDEX = 63
_MAX_SPEAKER_LABELS = 16

SYSTEM_PROMPT = """\
You are a meticulous transcript proofreader for a video studio. You are given raw \
speech-to-text output and must correct ONLY mistakes the recogniser made, never the \
speaker's actual words.

CORRECT a segment only when the text is clearly a recognition error:
- a wrong sound-alike / homophone that does not fit the sentence;
- a garbled or misspelled proper noun, name, brand, place, or technical term, but \
only when the correct form is unambiguous from context;
- a word the recogniser clearly split or merged incorrectly;
- missing sentence punctuation where a sentence plainly ended.

DO NOT:
- rewrite, paraphrase, summarise, translate, or "improve" the language;
- remove filler words, hesitations, slang, or repetition;
- fix grammar, style, or tone;
- change meaning, facts, names, or numbers;
- merge, split, reorder, or drop segments.

If a segment has no clear recognition error, OMIT it from `corrections`. An empty \
`corrections` list is the common, correct answer.

SPEAKER INFERENCE. When speaker labels are missing or clearly wrong, assign a \
consistent integer speaker index (0, 1, 2, ...) per distinct voice, using cues in the \
text: names, "my co-host", interviewer versus guest questions, pronouns, and \
turn-taking. When you can name a voice, also return `speakerLabels`, mapping the \
integer to a short role or name ("Host", "Guest", "Interviewer"). Never guess when the \
text gives no signal.

Return JSON only, matching the schema. Only include segments you actually changed.
"""


@dataclass
class RepairResult:
    """Cleaned segments plus what the pass changed and cost."""

    segments: list[dict[str, Any]] = field(default_factory=list)
    speaker_labels: dict[str, str] = field(default_factory=dict)
    corrections: int = 0
    usage: LlmUsage = field(default_factory=LlmUsage)


def repair_schema() -> dict[str, Any]:
    """JSON schema for one cleanup batch.

    `text` / `speaker` are optional so a correction can fix either independently.
    """
    return {
        "type": "object",
        "properties": {
            "corrections": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "segmentId": {"type": "string"},
                        "text": {
                            "type": "string",
                            "description": "Corrected text, only when it changed.",
                        },
                        "speaker": {
                            "type": "integer",
                            "description": "Inferred speaker index, when it changed.",
                        },
                    },
                    "required": ["segmentId"],
                },
            },
            "speakerLabels": {
                "type": "object",
                "additionalProperties": {"type": "string"},
                "description": "Optional map of speaker index to a short role or name.",
            },
        },
        "required": ["corrections"],
    }


def _segment_chars(segment: dict[str, Any]) -> int:
    return len(str(segment.get("text", ""))) + 32


def _batch(segments: list[dict[str, Any]], max_chars: int) -> list[list[dict[str, Any]]]:
    """Split segments into prompt-sized batches (never splitting a segment)."""
    batches: list[list[dict[str, Any]]] = []
    current: list[dict[str, Any]] = []
    size = 0
    for segment in segments:
        segment_size = _segment_chars(segment)
        if current and size + segment_size > max_chars:
            batches.append(current)
            current = []
            size = 0
        current.append(segment)
        size += segment_size
    if current:
        batches.append(current)
    return batches


def build_user_prompt(
    segments: list[dict[str, Any]], *, language: str, batch: int, total: int
) -> str:
    header = [
        "# Cleanup task",
        f"Spoken language: {language or 'unspecified'}",
        f"Batch {batch} of {total}",
        "",
        "# SEGMENTS (return a correction only when the recogniser made an error)",
    ]
    lines = [
        f"[{segment.get('segmentId')}] "
        f"{int(segment.get('startMs', 0))} -> {int(segment.get('endMs', 0))} "
        f"(speaker={segment.get('speaker')}): {segment.get('text', '')}"
        for segment in segments
    ]
    return "\n".join(header + lines)


def _valid_text(old: str, new: str) -> str | None:
    """Keep a corrected text only when it is a plausible minor edit of the original."""
    candidate = new.strip()
    if not candidate or candidate == old.strip():
        return None
    # A proofread fix is a small edit. A huge expansion means the model rewrote it.
    limit = max(60, int(len(old) * 1.5) + 40)
    if len(candidate) > limit:
        logger.warning("transcript repair: dropping oversized rewrite (%d chars)", len(candidate))
        return None
    return candidate


def _apply_batch(
    batch: list[dict[str, Any]], data: dict[str, Any]
) -> tuple[list[dict[str, Any]], int, dict[str, str]]:
    """Apply one batch's model output onto copies of its segments."""
    by_id = {str(segment.get("segmentId")): segment for segment in batch}
    corrections = data.get("corrections")
    if not isinstance(corrections, list):
        corrections = []

    changed = 0
    for entry in corrections:
        if not isinstance(entry, dict):
            continue
        segment = by_id.get(str(entry.get("segmentId")))
        if segment is None:
            continue
        touched = False
        old_text = str(segment.get("text", ""))
        new_text = entry.get("text")
        if isinstance(new_text, str):
            cleaned = _valid_text(old_text, new_text)
            if cleaned is not None:
                segment["text"] = cleaned
                touched = True
        speaker = entry.get("speaker")
        if isinstance(speaker, bool):
            speaker = None
        if isinstance(speaker, int) and 0 <= speaker <= _MAX_SPEAKER_INDEX:
            if segment.get("speaker") != speaker:
                segment["speaker"] = speaker
                touched = True
        if touched:
            changed += 1

    labels: dict[str, str] = {}
    raw_labels = data.get("speakerLabels")
    if isinstance(raw_labels, dict):
        for key, value in raw_labels.items():
            try:
                index = int(key)
            except (TypeError, ValueError):
                continue
            if 0 <= index <= _MAX_SPEAKER_INDEX and isinstance(value, str) and value.strip():
                labels[str(index)] = value.strip()[:60]
            if len(labels) >= _MAX_SPEAKER_LABELS:
                break
    return batch, changed, labels


async def repair_transcript(
    segments: list[dict[str, Any]],
    *,
    language: str,
    llm: LlmProvider,
    model: str,
    max_chars: int = 12_000,
) -> RepairResult:
    """Return cleaned copies of `segments` and any inferred speaker labels.

    Never raises: any batch failure leaves those segments untouched.
    """
    if not segments:
        return RepairResult(segments=list(segments))

    working = [dict(segment) for segment in segments]
    batches = _batch(working, max(1, max_chars))
    total_corrections = 0
    usage = LlmUsage()
    labels: dict[str, str] = {}

    for number, batch in enumerate(batches, start=1):
        try:
            completion = await llm.complete_json(
                model=model,
                prompt_version=REPAIR_PROMPT_VERSION,
                system=SYSTEM_PROMPT,
                user=build_user_prompt(batch, language=language, batch=number, total=len(batches)),
                schema=repair_schema(),
            )
        except Exception:  # noqa: BLE001 - cleanup must never cost a transcript
            logger.exception(
                "transcript repair: batch %d/%d failed; keeping raw text",
                number,
                len(batches),
            )
            continue
        usage = LlmUsage(
            input_tokens=usage.input_tokens + completion.usage.input_tokens,
            output_tokens=usage.output_tokens + completion.usage.output_tokens,
        )
        _, changed, batch_labels = _apply_batch(batch, completion.data)
        total_corrections += changed
        labels.update(batch_labels)

    logger.info(
        "transcript repair: %d correction(s) across %d batch(es)",
        total_corrections,
        len(batches),
    )
    return RepairResult(
        segments=working,
        speaker_labels=labels,
        corrections=total_corrections,
        usage=usage,
    )


__all__ = [
    "REPAIR_PROMPT_VERSION",
    "RepairResult",
    "build_user_prompt",
    "repair_schema",
    "repair_transcript",
]
