"""Reviewer base: shared rubric, output schema, and model-output normalisation.

One reviewer per analysis dimension. A reviewer is a single structured Gemini call
over a transcript window (tier 1 in `docs/technical-design/backend-plan.md` section 8);
tier 2 (multimodal deep review of a clip) is the separate `segment-review` flow.

Two things live here so they cannot drift between the thirteen reviewers:

- the shared 0-10 anchor rubric, which stops every score collapsing to 7
- `normalize_findings`, which turns untrusted model output into `Finding` records
  with clamped timestamps, bounded scores, and resolved segment ids.
"""

import logging
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any, Protocol
from uuid import uuid4

from app.providers.base import LlmProvider, LlmUsage
from app.schemas.analysis import (
    AnalysisDimension,
    Finding,
    FindingEvidence,
    Severity,
)

logger = logging.getLogger(__name__)

#: Bumped whenever reviewer prompts change in a way that alters scores.
REVIEWER_PROMPT_VERSION = "reviewers-v1"

#: Bumped whenever the model/prompt configuration changes as a whole.
MODEL_CONFIG_VERSION = "analysis-v1"

_SEVERITY_VALUES = {severity.value for severity in Severity}

FINDINGS_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "findings": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "segmentId": {"type": "string"},
                    "startMs": {"type": "integer"},
                    "endMs": {"type": "integer"},
                    "score": {"type": "number"},
                    "confidence": {"type": "number"},
                    "severity": {
                        "type": "string",
                        "enum": [severity.value for severity in Severity],
                    },
                    "findingType": {"type": "string"},
                    "evidence": {
                        "type": "object",
                        "properties": {
                            "quote": {"type": "string"},
                            "explanation": {"type": "string"},
                        },
                        "required": ["quote", "explanation"],
                    },
                    "suggestion": {"type": "string"},
                    "citations": {
                        "type": "array",
                        "items": {"type": "object"},
                    },
                },
                "required": [
                    "segmentId",
                    "startMs",
                    "endMs",
                    "score",
                    "confidence",
                    "severity",
                    "findingType",
                    "evidence",
                    "suggestion",
                ],
            },
        }
    },
    "required": ["findings"],
}

SCORE_ANCHORS = """\
SCORE ANCHORS - use the whole range; do not cluster around 7:
  9.0-10.0  Excellent. Publishable as-is.
  8.0-8.9   Strong. At most one minor nit.
  6.0-7.9   Acceptable. One clear improvement would help.
  4.0-5.9   Weak. A viewer would notice the problem.
  2.0-3.9   Poor. A serious problem.
  0.0-1.9   Broken. Fix before publishing.

SEVERITY - how bad the problem is, judged separately from the score:
  none      No problem here. Use for strengths and for stretches that are simply fine.
  low       Minor. Worth a note, not urgent.
  medium    Noticeable. Should be fixed.
  high      Serious. Will cost the creator viewers, trust, or reach.
  critical  Dangerous or disqualifying. Fix before this is published."""

OUTPUT_RULES = """\
OUTPUT RULES:
1. Report findings ONLY for the segments listed under REVIEW WINDOW. Segments under
   CONTEXT are for continuity of understanding; never report them.
2. Cover the whole REVIEW WINDOW, in order. Emit an observation for every coherent
   span, including spans that are fine (severity "none"). Merge neighbouring segments
   that share one judgement into a single span.
3. Every finding must quote the exact words it is about, at most 25 words.
4. startMs and endMs are milliseconds and must fall inside the quoted words and
   inside the segment times you were given. endMs > startMs.
5. score is quality on the anchors above: higher is better.
6. suggestion is one concrete action the creator can take, or "" when severity is "none".
7. Never invent facts, names, numbers, quotes, or sources. If a claim cannot be
   settled from the transcript alone, use findingType "needs_manual_verification".
8. Return JSON only, matching the schema you are given. No markdown, no commentary."""


@dataclass(frozen=True)
class SegmentRef:
    """One transcript segment as the reviewer sees it."""

    segment_id: str
    start_ms: int
    end_ms: int
    text: str


@dataclass(frozen=True)
class ReviewContext:
    """Everything a reviewer needs for one window of the transcript."""

    persona: str
    platform: str
    audience: str
    language: str
    duration_ms: int
    segments: tuple[SegmentRef, ...]
    context_segments: tuple[SegmentRef, ...] = ()


@dataclass(frozen=True)
class ReviewResult:
    """Findings for one reviewer call plus what the call cost."""

    findings: tuple[Finding, ...] = ()
    usage: LlmUsage = field(default_factory=LlmUsage)


class Reviewer(Protocol):
    dimension: AnalysisDimension

    async def review(
        self, context: ReviewContext, *, reviewer_run_id: str = ""
    ) -> ReviewResult: ...


def dimension_label(dimension: AnalysisDimension) -> str:
    return dimension.value.replace("_", " ").title()


def build_system_prompt(dimension: AnalysisDimension, focus: str) -> str:
    """Shared role + anchors + rules, with the dimension rubric spliced in."""
    return "\n\n".join(
        [
            (
                "You are one of thirteen specialist reviewers in a creator video review "
                f"panel. Your only job today is {dimension_label(dimension)} "
                f"({dimension.value}). Be specific, evidence-first, and strict: vague "
                "praise and vague criticism are both useless to the creator."
            ),
            f"WHAT TO REVIEW FOR ({dimension_label(dimension)}):\n{focus.strip()}",
            SCORE_ANCHORS,
            OUTPUT_RULES,
        ]
    )


def build_user_prompt(context: ReviewContext, dimension: AnalysisDimension) -> str:
    """Assemble the transcript window and the creator context."""
    header = [
        f"# Review task: {dimension_label(dimension)} ({dimension.value})",
        f"Target platform: {context.platform or 'unspecified'}",
        f"Spoken language: {context.language or 'unspecified'}",
        f"Video duration: {context.duration_ms} ms",
    ]
    if context.audience:
        header.append(f"Intended audience: {context.audience}")
    if context.persona:
        header.append(f"Creator persona:\n{context.persona}")

    lines = ["\n".join(header), "", "# REVIEW WINDOW (report on these)"]
    lines.extend(_format_segments(context.segments))
    if context.context_segments:
        lines += ["", "# CONTEXT ONLY (do not report findings for these)"]
        lines.extend(_format_segments(context.context_segments))
    return "\n".join(lines)


def _format_segments(segments: Sequence[SegmentRef]) -> list[str]:
    return [
        f"[{segment.segment_id}] {segment.start_ms} -> {segment.end_ms}: {segment.text}"
        for segment in segments
    ]


def severity_for_score(score: float) -> Severity:
    """Fallback severity for model output that omits or mangles it.

    Mirrors the score bands from `backend-plan.md` section 9 so an unlabelled
    observation still colours the heatmap sensibly.
    """
    if score >= 8:
        return Severity.none
    if score >= 6:
        return Severity.low
    if score >= 4:
        return Severity.medium
    if score >= 2:
        return Severity.high
    return Severity.critical


def resolve_segment(
    start_ms: int, segments: Sequence[SegmentRef]
) -> SegmentRef | None:
    """The segment that contains `start_ms`, if any."""
    for segment in segments:
        if segment.start_ms <= start_ms < segment.end_ms:
            return segment
    return None


def _as_int(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _as_float(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def normalize_findings(
    raw: dict[str, Any],
    *,
    dimension: AnalysisDimension,
    reviewer_run_id: str,
    segments: Sequence[SegmentRef],
    duration_ms: int,
) -> list[Finding]:
    """Turn untrusted model output into validated `Finding` records.

    Guarantees on every emitted finding: score in [0, 10], confidence in [0, 1],
    timestamps ordered and inside `[0, duration_ms]`, a severity from the enum, and a
    `segmentId` that resolves to a real segment (or None). Entries that cannot be
    salvaged are dropped rather than guessed at.
    """
    entries = raw.get("findings") if isinstance(raw, dict) else None
    if not isinstance(entries, list):
        logger.warning("reviewer %s: response has no findings array", dimension.value)
        return []

    findings: list[Finding] = []
    for entry in entries:
        finding = _normalize_one(
            entry,
            dimension=dimension,
            reviewer_run_id=reviewer_run_id,
            segments=segments,
            duration_ms=duration_ms,
        )
        if finding is not None:
            findings.append(finding)
    return findings


def _normalize_one(
    entry: Any,
    *,
    dimension: AnalysisDimension,
    reviewer_run_id: str,
    segments: Sequence[SegmentRef],
    duration_ms: int,
) -> Finding | None:
    if not isinstance(entry, dict):
        return None

    score = _as_float(entry.get("score"))
    if score is None:
        logger.warning("reviewer %s: dropping finding without a score", dimension.value)
        return None
    score = _clamp(score, 0.0, 10.0)

    confidence = _as_float(entry.get("confidence"))
    confidence = _clamp(confidence if confidence is not None else 0.5, 0.0, 1.0)

    severity_value = entry.get("severity")
    if isinstance(severity_value, str) and severity_value in _SEVERITY_VALUES:
        severity = Severity(severity_value)
    else:
        severity = severity_for_score(score)

    declared_id = entry.get("segmentId")
    declared_segment = _segment_by_id(declared_id, segments)

    start_ms = _as_int(entry.get("startMs"))
    end_ms = _as_int(entry.get("endMs"))
    if start_ms is None or end_ms is None or end_ms <= start_ms:
        if declared_segment is None:
            logger.warning(
                "reviewer %s: dropping finding with unusable timestamps", dimension.value
            )
            return None
        start_ms, end_ms = declared_segment.start_ms, declared_segment.end_ms

    start_ms = int(_clamp(start_ms, 0, max(0, duration_ms)))
    end_ms = int(_clamp(end_ms, 0, max(0, duration_ms)))
    if end_ms <= start_ms:
        logger.warning("reviewer %s: dropping finding outside the video", dimension.value)
        return None

    segment = resolve_segment(start_ms, segments) or declared_segment

    raw_evidence = entry.get("evidence")
    evidence: dict[str, Any] = raw_evidence if isinstance(raw_evidence, dict) else {}
    citations = entry.get("citations")
    if not isinstance(citations, list):
        citations = []
    citations = [item for item in citations if isinstance(item, dict)]

    return Finding(
        findingId=uuid4().hex,
        dimension=dimension,
        reviewerRunId=reviewer_run_id,
        segmentId=segment.segment_id if segment else None,
        startMs=start_ms,
        endMs=end_ms,
        score=round(score, 2),
        confidence=round(confidence, 2),
        severity=severity,
        findingType=str(entry.get("findingType") or "observation")[:120],
        evidence=FindingEvidence(
            quote=str(evidence.get("quote") or "")[:2000],
            explanation=str(evidence.get("explanation") or "")[:2000],
        ),
        suggestion=str(entry.get("suggestion") or "")[:2000],
        citations=citations,
    )


def _segment_by_id(
    segment_id: Any, segments: Sequence[SegmentRef]
) -> SegmentRef | None:
    if not isinstance(segment_id, str):
        return None
    for segment in segments:
        if segment.segment_id == segment_id:
            return segment
    return None


class LlmReviewer:
    """A reviewer that runs one structured LLM call over one transcript window.

    Subclasses set `dimension` and `focus`; everything else is shared so the
    thirteen reviewers cannot drift apart in rubric or output handling.
    """

    dimension: AnalysisDimension
    focus: str = ""

    def __init__(self, llm: LlmProvider, *, model: str) -> None:
        self.llm = llm
        self.model = model

    async def review(
        self, context: ReviewContext, *, reviewer_run_id: str = ""
    ) -> ReviewResult:
        completion = await self.llm.complete_json(
            model=self.model,
            prompt_version=REVIEWER_PROMPT_VERSION,
            system=build_system_prompt(self.dimension, self.focus),
            user=build_user_prompt(context, self.dimension),
            schema=FINDINGS_SCHEMA,
        )
        findings = normalize_findings(
            completion.data,
            dimension=self.dimension,
            reviewer_run_id=reviewer_run_id,
            segments=context.segments,
            duration_ms=context.duration_ms,
        )
        return ReviewResult(findings=tuple(findings), usage=completion.usage)


__all__ = [
    "FINDINGS_SCHEMA",
    "LlmReviewer",
    "MODEL_CONFIG_VERSION",
    "OUTPUT_RULES",
    "REVIEWER_PROMPT_VERSION",
    "SCORE_ANCHORS",
    "ReviewContext",
    "ReviewResult",
    "Reviewer",
    "SegmentRef",
    "build_system_prompt",
    "build_user_prompt",
    "dimension_label",
    "normalize_findings",
    "resolve_segment",
    "severity_for_score",
]
