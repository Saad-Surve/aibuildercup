"""Reviewer base: shared rubric, output schema, and model-output normalisation.

One reviewer per analysis dimension. A reviewer is a single structured Gemini call
over a transcript window (`docs/technical-design/backend-plan.md` section 8); it may
pull frames or a short clip mid-review through the FFmpeg function-calling tools, so
the multimodal pass lives inside the same analysis run, not a separate flow.

Two things live here so they cannot drift between the thirteen reviewers:

- the shared 0-10 anchor rubric, which stops every score collapsing to 7
- `normalize_findings`, which turns untrusted model output into `Finding` records
  with clamped timestamps, bounded scores, and resolved segment ids.
"""

import asyncio
import logging
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any, Protocol
from uuid import uuid4

from app.providers.base import GroundingInfo, LlmProvider, LlmUsage, MediaPart
from app.schemas.analysis import (
    AnalysisDimension,
    Finding,
    FindingEvidence,
    Severity,
)
from app.services.video_tools import (
    ContextArtifactStore,
    MediaToolkit,
    review_tool_specs,
)

logger = logging.getLogger(__name__)

#: Bumped whenever reviewer prompts change in a way that alters scores.
REVIEWER_PROMPT_VERSION = "reviewers-v4"

#: Bumped whenever the model/prompt configuration changes as a whole.
MODEL_CONFIG_VERSION = "analysis-v4"

_SEVERITY_VALUES = {severity.value for severity in Severity}

#: The panel role. `{dimension_label}` / `{dimension_value}` are the only substitutions.
ROLE = (
    "You are an elite video script and retention analyst on a creator advisory panel. "
    "Your sole focus today is {dimension_label} ({dimension_value}).\n\n"
    "GUIDELINES:\n"
    "1. Speak to the medium: this is spoken conversational audio for digital video, not "
    "an academic essay. Natural contractions, rhetorical questions, conversational "
    "tangents, and informal registers are expected and encouraged when they sustain "
    "attention.\n"
    "2. Be surgically specific: every critique needs a direct quote and an immediate, "
    "rewrite-ready suggestion.\n"
    "3. Reason before grading: analyze why an element succeeds or fails before assigning "
    "severity and a score."
)

SCORE_ANCHORS = """\
EVALUATION SCALE - discrete 1-5, higher is better:
  5  Outstanding. Masterclass execution. Keep as-is.                  (severity: none)
  4  Strong. Engaging and effective; minor polish possible.           (severity: none)
  3  Needs polish. Noticeable friction; distracts or slows pacing.    (severity: low or medium)
  2  Poor. Actively loses viewers, trust, or clarity; rewrite it.     (severity: high)
  1  Disqualifying. Broken, deceptive, legally hazardous, unwatchable. (severity: critical)

SEVERITY - judged separately from the score, how bad the problem is:
  none      No problem. Use only for an exceptional strength (score 5).
  low       Minor. Worth a note, not urgent.
  medium    Noticeable. Should be fixed.
  high      Serious. Will cost the creator viewers, trust, or reach.
  critical  Dangerous or disqualifying. Fix before this is published.

REPORTING THRESHOLD - exception-first, do NOT narrate the whole transcript:
  a) A concrete friction point or flaw (severity low/medium/high/critical), or
  b) An exceptional, high-impact technique worth reinforcing (score 5, severity none).
  Ordinary, fine sentences get no finding. Silence is not a finding."""

VISUAL_TOOLS_PROMPT = """\
FOOTAGE TOOLS. You can inspect the video itself, not just the transcript. Two tools are
available during this review:
  - extract_frame(timestampMs): one still frame; use for on-screen text, a chart, a face,
    a costume, a product, or any single moment.
  - cut_clip(timestampMs): a short clip around the moment (~{window} seconds either side);
    use when motion, a reaction, an edit, or timing matters.
CALL A TOOL whenever a judgement depends on something you cannot settle from the words
alone. In particular, before you assign severity "high" or "critical" to a finding whose
evidence could be visual, fetch the footage and confirm. Do not call the tools for purely
spoken-language judgements. You may make at most {max_calls} call(s); one well-chosen clip
often beats several stills. After the footage comes back you will see it and produce the
final findings; use it to sharpen severity, not to narrow your coverage.

COVERAGE. Footage is an aid, not a gate. Report every genuine issue your dimension covers in
this window: if the transcript alone already justifies a finding, report it whether or not
you fetched footage; if the footage only changes how serious it is, adjust the severity and
still report it. Do not stop at the first finding when the window has more, and do not
withhold a finding just because you could not confirm it visually.
"""

OUTPUT_RULES = """\
OUTPUT RULES:
1. Report findings ONLY for the segments listed under REVIEW WINDOW. Segments under
   CONTEXT are for continuity of understanding; never report them.
2. Exception-first: emit a finding only for a real flaw, or for an exceptional
   strength (score 5). Leave ordinary, fine stretches unreported; do not emit filler
   observations. Merge neighbouring segments that share one judgement.
3. Every finding must quote the exact words it is about, at most 25 words.
4. startMs and endMs are milliseconds and must fall inside the quoted words and
   inside the segment times you were given. endMs > startMs.
5. score is the discrete 1-5 quality scale above; severity is judged separately.
6. suggestion is one concrete, rewrite-ready action, or "" only when severity is
   "none" (an exceptional strength).
7. Never invent facts, names, numbers, quotes, or sources. If a claim cannot be
   settled from the transcript alone, use findingType "needs_verification".
8. Return JSON only, matching the schema you are given. No markdown, no commentary."""

GROUNDING_PROMPT = """\
GROUNDING WITH GOOGLE SEARCH. You have Google Search, and you must use it. For every hard
factual claim (a statistic, a date, a scientific or causal mechanism, a universal or
superlative assertion):
- Search before you judge. Never decide a claim's truth from memory alone.
- Put the sources you actually used on each finding in `sources` (title + url). Quote only
  what the source supports; do not invent or guess a source.
- If the sources do not settle the claim, use findingType "needs_verification" instead of
  asserting a verdict.
- A clear source that contradicts the spoken claim is a "false_claim"; a source that backs
  an unusually well-evidenced claim is a "supported_claim" (severity none, score 5)."""


def findings_schema(
    finding_types: Sequence[str], *, grounded: bool = False
) -> dict[str, Any]:
    """JSON schema for one reviewer's output.

    Property order matters: autoregressive models generate keys in order, so `evidence`
    (reasoning) precedes `severity`/`score` to force reason-then-grade. `findingType` is
    constrained to that reviewer's vocabulary so the model cannot invent types. When
    `grounded` is set, each finding also carries the `sources` it was verified against.
    """
    item_properties: dict[str, Any] = {
        "segmentId": {"type": "string"},
        "startMs": {"type": "integer"},
        "endMs": {"type": "integer"},
        "evidence": {
            "type": "object",
            "properties": {
                "quote": {"type": "string", "maxLength": 300},
                "critique_and_reasoning": {
                    "type": "string",
                    "description": (
                        "Analyze why this specific line succeeds or fails "
                        "before scoring."
                    ),
                },
            },
            "required": ["quote", "critique_and_reasoning"],
        },
        "findingType": {
            "type": "string",
            "enum": list(finding_types) or ["observation"],
        },
        "severity": {
            "type": "string",
            "enum": [severity.value for severity in Severity],
        },
        "score": {"type": "integer", "minimum": 1, "maximum": 5},
        "suggestion": {
            "type": "string",
            "description": (
                "Concrete rewrite or editorial action; empty only when severity is none."
            ),
        },
    }
    required = [
        "segmentId",
        "startMs",
        "endMs",
        "evidence",
        "findingType",
        "severity",
        "score",
        "suggestion",
    ]
    if grounded:
        item_properties["sources"] = {
            "type": "array",
            "description": "Web sources you used to verify this claim (title + url).",
            "items": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "url": {"type": "string"},
                },
                "required": ["title", "url"],
            },
        }
        required.append("sources")
    return {
        "type": "object",
        "properties": {
            "findings": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": item_properties,
                    "required": required,
                },
            }
        },
        "required": ["findings"],
    }


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
    #: Packaging context: a hook can only be judged against the title/thumbnail promise.
    video_title: str = ""
    thumbnail_concept: str = ""


@dataclass(frozen=True)
class ToolCallRecord:
    """One footage tool the reviewer called, for persistence and the UI.

    `content_path` is the Cloud Storage object holding the frame/clip (empty when the
    call failed or no store was configured).
    """

    tool: str
    timestamp_ms: int = 0
    label: str = ""
    mime_type: str = ""
    content_path: str = ""
    ok: bool = True
    error: str = ""


@dataclass(frozen=True)
class ReviewResult:
    """Findings for one reviewer call plus what the call cost and fetched."""

    findings: tuple[Finding, ...] = ()
    usage: LlmUsage = field(default_factory=LlmUsage)
    tool_calls: tuple[ToolCallRecord, ...] = ()
    grounding: GroundingInfo | None = None

    @property
    def visual_context_count(self) -> int:
        return len(self.tool_calls)


class Reviewer(Protocol):
    dimension: AnalysisDimension

    async def review(
        self, context: ReviewContext, *, reviewer_run_id: str = ""
    ) -> ReviewResult: ...


#: Display labels. Kept explicit so acronyms do not render as `Seo` / `Cta`.
DIMENSION_LABELS: dict[AnalysisDimension, str] = {
    AnalysisDimension.truth_evidence: "Truth & Evidence",
    AnalysisDimension.clarity: "Spoken Clarity",
    AnalysisDimension.pacing_retention: "Pacing & Retention",
    AnalysisDimension.legal_safety: "Legal & Safety",
    AnalysisDimension.cultural_localization: "Culture & Localization",
    AnalysisDimension.platform_fit: "Platform Dynamics",
    AnalysisDimension.audience_brand: "Audience & Brand",
    AnalysisDimension.emotional_impact: "Emotional Impact",
    AnalysisDimension.conversion_cta: "Conversion & CTA",
}


def dimension_label(dimension: AnalysisDimension) -> str:
    return DIMENSION_LABELS.get(
        dimension, dimension.value.replace("_", " ").title()
    )


def build_system_prompt(
    dimension: AnalysisDimension,
    focus: str,
    *,
    visual_tools: bool = False,
    max_tool_calls: int = 0,
    clip_window_seconds: int = 5,
    grounding: bool = False,
) -> str:
    """Shared role + anchors + rules, with the dimension rubric spliced in.

    `visual_tools` adds the footage tools; `grounding` adds the Google Search policy.
    """
    sections = [
        ROLE.format(
            dimension_label=dimension_label(dimension),
            dimension_value=dimension.value,
        ),
        f"WHAT TO REVIEW FOR ({dimension_label(dimension)}):\n{focus.strip()}",
        SCORE_ANCHORS,
        OUTPUT_RULES,
    ]
    if visual_tools:
        sections.append(
            VISUAL_TOOLS_PROMPT.format(
                window=max(1, clip_window_seconds),
                max_calls=max(1, max_tool_calls),
            )
        )
    if grounding:
        sections.append(GROUNDING_PROMPT)
    return "\n\n".join(sections)


def build_user_prompt(context: ReviewContext, dimension: AnalysisDimension) -> str:
    """Assemble the transcript window and the creator context."""
    header = [
        f"# Review task: {dimension_label(dimension)} ({dimension.value})",
        f"Video title: {context.video_title or 'untitled'}",
        f"Target platform: {context.platform or 'unspecified'}",
        f"Spoken language: {context.language or 'unspecified'}",
        f"Video duration: {context.duration_ms} ms",
    ]
    if context.thumbnail_concept:
        header.append(f"Thumbnail concept: {context.thumbnail_concept}")
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

    Mirrors the 1-5 scale so an unlabelled observation still colours the heatmap sensibly.
    """
    if score >= 4:
        return Severity.none
    if score >= 3:
        return Severity.low
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

    Guarantees on every emitted finding: score in [1, 5], confidence in [0, 1],
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


def _normalize_citations(entry: dict[str, Any]) -> list[dict[str, Any]]:
    """Collect citations from either an explicit `citations` list or grounded `sources`."""
    citations: list[dict[str, Any]] = []
    for item in entry.get("citations") or []:
        if isinstance(item, dict):
            citations.append(item)
    for source in entry.get("sources") or []:
        if not isinstance(source, dict):
            continue
        url = str(source.get("url") or source.get("uri") or "").strip()
        title = str(source.get("title") or source.get("domain") or "").strip()
        if url or title:
            citations.append({"title": title or url, "url": url})
    return citations


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

    raw_score = _as_float(entry.get("score"))
    if raw_score is None:
        logger.warning("reviewer %s: dropping finding without a score", dimension.value)
        return None
    score = int(round(_clamp(raw_score, 1.0, 5.0)))

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
    citations = _normalize_citations(entry)

    return Finding(
        findingId=uuid4().hex,
        dimension=dimension,
        reviewerRunId=reviewer_run_id,
        segmentId=segment.segment_id if segment else None,
        startMs=start_ms,
        endMs=end_ms,
        score=score,
        confidence=round(confidence, 2),
        severity=severity,
        findingType=str(entry.get("findingType") or "observation")[:120],
        evidence=FindingEvidence(
            quote=str(evidence.get("quote") or "")[:2000],
            critique_and_reasoning=str(
                evidence.get("critique_and_reasoning")
                or evidence.get("explanation")
                or ""
            )[:2000],
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
    """A reviewer that runs a structured, tool-enabled review of one window.

    Subclasses set `dimension`, `focus`, and `finding_types`; everything else is shared so
    the reviewers cannot drift apart in rubric, schema, or output handling. When a
    `visual_tools` toolkit is supplied, the reviewer can call its two footage tools during
    the review - the model decides, the loop is bounded - and the calls ride back on the
    result for persistence and the UI.
    """

    dimension: AnalysisDimension
    focus: str = ""
    #: Allowed `findingType` values. Constrains the schema so the model cannot invent types.
    finding_types: tuple[str, ...] = ()
    #: Subclasses that benefit from web verification set this; the worker still gates it.
    supports_grounding: bool = False

    def __init__(
        self,
        llm: LlmProvider,
        *,
        model: str,
        visual_tools: MediaToolkit | None = None,
        context_store: ContextArtifactStore | None = None,
        grounding_enabled: bool = False,
    ) -> None:
        self.llm = llm
        self.model = model
        self.visual_tools = visual_tools
        self.context_store = context_store
        self.grounding = bool(grounding_enabled and type(self).supports_grounding)

    async def review(
        self, context: ReviewContext, *, reviewer_run_id: str = ""
    ) -> ReviewResult:
        system = build_system_prompt(
            self.dimension,
            self.focus,
            visual_tools=self.visual_tools is not None,
            max_tool_calls=self.visual_tools.max_requests if self.visual_tools else 0,
            clip_window_seconds=(
                self.visual_tools.window_seconds if self.visual_tools else 5
            ),
            grounding=self.grounding,
        )
        user = build_user_prompt(context, self.dimension)
        schema = findings_schema(self.finding_types, grounded=self.grounding)

        if self.visual_tools is None:
            completion = await self.llm.complete_json(
                model=self.model,
                prompt_version=REVIEWER_PROMPT_VERSION,
                system=system,
                user=user,
                schema=schema,
                grounding=self.grounding,
            )
            return ReviewResult(
                findings=tuple(self._normalize(completion.data, context, reviewer_run_id)),
                usage=completion.usage,
                grounding=completion.grounding,
            )

        toolkit = self.visual_tools
        store = self.context_store
        records: list[ToolCallRecord] = []
        index = 0

        async def execute(name: str, arguments: dict[str, Any]) -> list[MediaPart]:
            nonlocal index
            parts = await toolkit.execute(name, arguments)
            media: list[MediaPart] = []
            for part in parts:
                path = ""
                if store is not None:
                    try:
                        path = await asyncio.to_thread(
                            store.save,
                            part,
                            reviewer_run_id=reviewer_run_id,
                            tool=name,
                            index=index,
                        )
                    except Exception:  # noqa: BLE001 - storage must not lose the review
                        logger.warning(
                            "reviewer %s: could not store context artifact",
                            self.dimension.value,
                            exc_info=True,
                        )
                records.append(
                    ToolCallRecord(
                        tool=name,
                        timestamp_ms=_as_int(arguments.get("timestampMs")) or 0,
                        label=part.label,
                        mime_type=part.mime_type,
                        content_path=path,
                        ok=True,
                    )
                )
                media.append(part)
                index += 1
            return media

        completion = await self.llm.complete_json_with_tools(
            model=self.model,
            prompt_version=REVIEWER_PROMPT_VERSION,
            system=system,
            user=user,
            schema=schema,
            tools=review_tool_specs(clip_window_seconds=toolkit.window_seconds),
            execute=execute,
            max_tool_rounds=toolkit.max_rounds,
            max_tool_calls=toolkit.max_requests,
            grounding=self.grounding,
        )
        return ReviewResult(
            findings=tuple(self._normalize(completion.data, context, reviewer_run_id)),
            usage=completion.usage,
            tool_calls=tuple(records),
            grounding=completion.grounding,
        )

    def _normalize(
        self, raw: dict[str, Any], context: ReviewContext, reviewer_run_id: str
    ) -> list[Finding]:
        return normalize_findings(
            raw,
            dimension=self.dimension,
            reviewer_run_id=reviewer_run_id,
            segments=context.segments,
            duration_ms=context.duration_ms,
        )


__all__ = [
    "DIMENSION_LABELS",
    "GROUNDING_PROMPT",
    "LlmReviewer",
    "MODEL_CONFIG_VERSION",
    "OUTPUT_RULES",
    "REVIEWER_PROMPT_VERSION",
    "ROLE",
    "SCORE_ANCHORS",
    "ReviewContext",
    "ReviewResult",
    "Reviewer",
    "SegmentRef",
    "ToolCallRecord",
    "VISUAL_TOOLS_PROMPT",
    "build_system_prompt",
    "build_user_prompt",
    "dimension_label",
    "findings_schema",
    "normalize_findings",
    "resolve_segment",
    "severity_for_score",
]
