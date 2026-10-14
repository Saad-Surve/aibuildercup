"""Shared, frozen single-prompt review used by the rubric arm and product coordinator."""

from collections import defaultdict
from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any

from app.agents.reviewer_base import (
    GROUNDING_PROMPT,
    SCORE_ANCHORS,
    SegmentRef,
    dimension_label,
    findings_schema,
    normalize_findings,
)
from app.agents.reviewer_registry import REVIEWER_CLASSES
from app.schemas.analysis import ACTIVE_DIMENSIONS, AnalysisDimension, Finding

BASELINE_PROMPT_VERSION = "editorial-baseline-v1"
RUBRIC_PROMPT_VERSION = "rubric-v1"
MAX_RUBRIC_PROMPT_CHARS = 100_000
RUBRIC_MAX_OUTPUT_TOKENS = 16_384

#: One line per dimension for the plain baseline: what a reasonable user would write.
DIMENSION_BLURBS: dict[AnalysisDimension, str] = {
    AnalysisDimension.truth_evidence: "factual errors and unsupported claims",
    AnalysisDimension.clarity: "unclear explanations, unexplained jargon, hard-to-follow phrasing",
    AnalysisDimension.pacing_retention: "weak hooks, slow or repetitive stretches, tangents, "
    "promises that are not kept",
    AnalysisDimension.legal_safety: "legal, medical, financial or safety risks",
    AnalysisDimension.cultural_localization: "assumptions about location or culture that a "
    "worldwide audience would not share",
    AnalysisDimension.platform_fit: "how well the video fits the platform it is published on",
    AnalysisDimension.audience_brand: "fit with the intended audience and the stated tone",
    AnalysisDimension.emotional_impact: "emotional flatness or tone that does not fit the moment",
    AnalysisDimension.conversion_cta: "calls to action and next steps that serve the creator's "
    "goal",
}

BASELINE_RULES = """\
OUTPUT RULES:
1. Review the whole video. Report only real problems or exceptional strengths (score 5, severity
   none); do not narrate ordinary stretches and never invent issues to fill a quota.
2. For a spoken issue, quote the exact words (at most 25 words); for an omission, the quote may
   be empty. startMs and endMs are milliseconds from the start of the video; mark the actual span,
   or where an omission belongs. segmentId is the nearest transcript segment.
3. Set `dimension` to the area the issue belongs to. score is the 1-5 scale above; severity is
   judged separately.
4. critique_and_reasoning is 1-2 short sentences. suggestion is one concrete edit: what to trim or
   move, replacement wording, or exactly what to add here. Do not invent facts, names, numbers or
   sources. Return JSON only, matching the schema."""


def all_finding_types() -> list[str]:
    seen: dict[str, None] = {}
    for dimension in ACTIVE_DIMENSIONS:
        for finding_type in REVIEWER_CLASSES[dimension].finding_types:
            seen.setdefault(finding_type)
    return list(seen)


def baseline_schema(*, grounded: bool) -> dict[str, Any]:
    """The reviewers' finding shape plus the `dimension` a single prompt must choose itself."""
    schema = findings_schema(all_finding_types(), grounded=grounded)
    item = schema["properties"]["findings"]["items"]
    item["properties"]["dimension"] = {
        "type": "string",
        "enum": [dimension.value for dimension in ACTIVE_DIMENSIONS],
    }
    item["required"].append("dimension")
    return schema


def baseline_system(*, rubric: bool, grounded: bool) -> str:
    if rubric:
        areas = "\n\n".join(
            f"## {dimension_label(d)} (dimension: {d.value})\n{REVIEWER_CLASSES[d].focus.strip()}"
            for d in ACTIVE_DIMENSIONS
        )
        intro = "Review the video against all nine areas below, each with its own rubric."
    else:
        areas = "\n".join(
            f"- {dimension_label(d)} (dimension: {d.value}): {DIMENSION_BLURBS[d]}"
            for d in ACTIVE_DIMENSIONS
        )
        intro = "Review the video in these areas."
    sections = [
        "You are an expert video editor and script consultant reviewing a creator's video "
        "before it is published. The video is attached and its transcript is below. "
        f"{intro} Help the creator edit: explain the viewer friction, then give one change they "
        "can make at the marked moment, preserving their voice and intent.",
        areas,
        SCORE_ANCHORS,
        BASELINE_RULES,
    ]
    if grounded:
        sections.append(GROUNDING_PROMPT)
    return "\n\n".join(sections)


def baseline_user(label: dict[str, Any], segments: Sequence[SegmentRef]) -> str:
    header = [
        "# Review task: whole video",
        f"Video title: {label['title']}",
        f"Target platform: {label['platform']}",
        f"Spoken language: {label['language']}",
        f"Video duration: {label['durationMs']} ms",
        f"Review date: {datetime.now(UTC).date().isoformat()}. Filming date is not provided.",
        f"Creator's brief: {label['brief']}",
        f"Intended audience: {label['audience']}",
    ]
    lines = [f"[{s.segment_id}] {s.start_ms} -> {s.end_ms}: {s.text}" for s in segments]
    return "\n".join(header) + "\n\n# TRANSCRIPT\n" + "\n".join(lines)


def normalize_baseline(
    raw: dict[str, Any],
    segments: Sequence[SegmentRef],
    duration_ms: int,
    *,
    reviewer_run_id: str = "baseline",
) -> list[Finding]:
    """Normalise with the reviewers' own validator, grouped by the dimension the model chose."""
    entries = raw.get("findings") if isinstance(raw, dict) else None
    groups: dict[AnalysisDimension, list[Any]] = defaultdict(list)
    for entry in entries or []:
        try:
            groups[AnalysisDimension(str(entry.get("dimension")))].append(entry)
        except (ValueError, AttributeError):
            continue
    findings = []
    for dimension, group in groups.items():
        findings.extend(
            normalize_findings(
                {"findings": group},
                dimension=dimension,
                reviewer_run_id=reviewer_run_id,
                segments=segments,
                duration_ms=duration_ms,
            )
        )
    findings.sort(key=lambda finding: finding.startMs)
    return findings
