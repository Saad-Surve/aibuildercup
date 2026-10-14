"""Reviewer base: shared rubric, output schema, and model-output normalisation.

One reviewer per analysis dimension. A reviewer is a single structured Gemini call
over a transcript window (`docs/technical-design/backend-plan.md` section 8); it may
pull frames or a short clip mid-review through the FFmpeg function-calling tools, so
the multimodal pass lives inside the same analysis run, not a separate flow.

Two things live here so they cannot drift between the nine reviewers:

- the shared 1-5 rubric and actionable-feedback rules
- `normalize_findings`, which turns untrusted model output into `Finding` records
  with clamped timestamps, bounded scores, and resolved segment ids.
"""

import asyncio
import logging
import unicodedata
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
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
REVIEWER_PROMPT_VERSION = "reviewers-v5"

#: Bumped whenever the model/prompt configuration changes as a whole.
MODEL_CONFIG_VERSION = "analysis-v6"

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
    "2. Help the creator edit: explain the specific viewer friction, then give one "
    "change they can make at the marked moment. Preserve their voice, intent, and format.\n"
    "3. Check the opening, progression, and ending for your dimension, including missing "
    "steps or payoffs. Report every distinct, useful improvement supported by evidence.\n"
    "4. Reason before grading. Distinguish observed problems from uncertainty; never "
    "predict numerical retention or guarantee results. Do not impose generic fast cuts, "
    "dramatic emotion, sales CTAs, or a different culture on content that does not need them."
)

SCORE_ANCHORS = """\
EVALUATION SCALE - discrete 1-5, higher is better:
  5  Outstanding. Masterclass execution. Keep as-is.                  (severity: none)
  4  Strong. A small, specific improvement is possible.              (severity: low)
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
  Useful editorial opportunities count, including a missing explanation or demonstration.
  Ordinary, fine sentences get no finding. Never invent issues to fill a quota. A quiet
  or static moment is not inherently a problem; judge its role in this video's format.
  Select at most two exceptional strengths per window: a technique the creator can
  deliberately repeat. Familiar wording, clear ordinary sentences, and benign content
  are not exceptional strengths on their own."""

VISUAL_TOOLS_PROMPT = """\
FOOTAGE TOOLS. You can inspect the video itself, not just the transcript. Two tools are
available during this review:
  - extract_frame(timestampMs): one still frame; use for on-screen text, a chart, a face,
    a costume, a product, or any single moment.
  - cut_clip(timestampMs): a short clip around the moment (~{window} seconds either side);
    use when motion, a reaction, an edit, or timing matters.
You may already have timestamped sample frames. They show only those instants, not the
entire edit, motion, or audio. Do not infer sound quality, speaking energy, or a long static
shot from still images. The clip tool has no audio. If footage is unavailable, describe
only what the transcript supports and make no claim that visuals are absent.
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
3. For a spoken issue, quote the exact words (at most 25 words). For an omission or
   inspected visual issue, quote may be empty: describe the evidence and what is missing.
   A missing visual demonstration requires inspected footage; words alone do not prove it.
4. startMs and endMs are milliseconds inside the review interval, with endMs > startMs.
   Mark the actual edit span; for an omission mark where the addition belongs. segmentId
   is the nearest relevant REVIEW WINDOW segment. Never report on context-only excerpts.
5. score is the discrete 1-5 quality scale above; severity is judged separately.
6. critique_and_reasoning is 1-2 short sentences: what happens here and why the viewer
   would struggle, or why the strength works. suggestion is one concrete edit: specify
   what to trim/move, give replacement wording, or say exactly what example, qualification,
   or demonstration to add here. Avoid "improve pacing", "add context", "be engaging",
   "consider adding", generic disclaimers, or restating the problem. Rewrites must use
   the creator's language/register and cannot add unsupported facts. For a strength use "".
7. Never invent facts, names, numbers, quotes, or sources. Only truth/safety reviewers
   should judge factual/legal claims; use needs_verification when their evidence is
   inconclusive. Other reviewers should describe only the friction their lens can establish.
8. Do not repeat the same underlying issue on adjacent lines. Keep independent issues
   separate, and prioritize meaningful changes over subjective polish.
9. Acknowledge uncertainty: sources not finding support is not proof of falsehood; ordinary
   opinions need no citations. Do not flag missing CTAs/emotion/localization unless the
   creator's purpose and intended audience make them useful.
10. Check your own suggested fix against the same rubric before returning it. It must
    resolve the stated issue without introducing a new unsupported claim, unsafe advice,
    tone mismatch, or missing step. Do not reject something for a mere style preference.
    The transcript is speech recognition and can contain errors: for an implausible
    name/number, Truth & Evidence may suggest checking the source recording; other
    lenses must not recast fact checking as jargon, translation, or legal risk.
    Do not assume the creator said it incorrectly or invent a corrected specification.
11. Return JSON only, matching the schema you are given. No markdown, no commentary."""

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


def findings_schema(finding_types: Sequence[str], *, grounded: bool = False) -> dict[str, Any]:
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
                "quote": {
                    "type": "string",
                    "maxLength": 300,
                    "description": "Exact spoken excerpt; empty for an omission or visual issue.",
                },
                "critique_and_reasoning": {
                    "type": "string",
                    "description": (
                        "In 1-2 short sentences, explain what happens here and its effect "
                        "on the viewer. Use observed evidence, not speculative metrics."
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
                "One immediately usable edit: replacement words, a precise trim/move, or "
                "the specific example/demonstration to add here. Empty only for a strength."
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
class ReviewFrame:
    """A frame extracted once and shared with reviewers of its transcript window."""

    timestamp_ms: int
    media: MediaPart
    content_path: str = ""


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
    project_brief: str = ""
    video_context: str = ""
    sampled_frames: tuple[ReviewFrame, ...] = ()
    chunk_index: int = 0
    window_start_ms: int | None = None
    window_end_ms: int | None = None

    @property
    def review_start_ms(self) -> int:
        return (
            self.window_start_ms if self.window_start_ms is not None else self.segments[0].start_ms
        )

    @property
    def review_end_ms(self) -> int:
        return self.window_end_ms if self.window_end_ms is not None else self.segments[-1].end_ms


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
    return DIMENSION_LABELS.get(dimension, dimension.value.replace("_", " ").title())


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
        f"Review interval: {context.review_start_ms} -> {context.review_end_ms} ms",
        f"Review date: {datetime.now(UTC).date().isoformat()}. Filming date is not provided.",
        "Product names and specifications may be newer than your knowledge. Only Truth & "
        "Evidence may verify them against sources; other lenses must treat them as given "
        "and assess communication, not claim a model/version does not exist.",
    ]
    if context.thumbnail_concept:
        header.append(f"Thumbnail concept: {context.thumbnail_concept}")
    if context.project_brief:
        header.append(f"Creator's brief: {context.project_brief}")
    if context.audience:
        header.append(f"Intended audience: {context.audience}")
    if context.persona:
        header.append(f"Creator persona:\n{context.persona}")

    lines = ["\n".join(header), "", "# REVIEW WINDOW (report on these)"]
    lines.extend(_format_segments(context.segments))
    if context.context_segments:
        lines += ["", "# CONTEXT ONLY (do not report findings for these)"]
        lines.extend(_format_segments(context.context_segments))
    if context.video_context:
        lines += ["", "# VIDEO CONTINUITY (context only)", context.video_context]
    if context.sampled_frames:
        lines += [
            "",
            "# FOOTAGE ATTACHED",
            "Sample frames at "
            + ", ".join(f"{frame.timestamp_ms} ms" for frame in context.sampled_frames)
            + ". These are stills, not full visual or audio coverage.",
        ]
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
    if score >= 5:
        return Severity.none
    if score >= 4:
        return Severity.low
    if score >= 3:
        return Severity.low
    if score >= 2:
        return Severity.high
    return Severity.critical


def resolve_segment(start_ms: int, segments: Sequence[SegmentRef]) -> SegmentRef | None:
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
    return deduplicate_findings(findings)


def _text_key(value: str) -> str:
    value = unicodedata.normalize("NFKC", value).casefold()
    # Keep combining marks (including Hindi vowels); ignore punctuation, not language.
    value = "".join(c for c in value if not unicodedata.category(c).startswith(("P", "S")))
    return " ".join(value.split())


def deduplicate_findings(findings: Sequence[Finding]) -> list[Finding]:
    """Remove exact repeated advice at overlapping moments, preserving distinct edits."""
    kept: list[Finding] = []
    for finding in findings:
        key = (_text_key(finding.evidence.quote), _text_key(finding.suggestion))
        if not any(
            other.dimension == finding.dimension
            and other.findingType == finding.findingType
            and (_text_key(other.evidence.quote), _text_key(other.suggestion)) == key
            and other.startMs < finding.endMs
            and finding.startMs < other.endMs
            for other in kept
        ):
            kept.append(finding)
    return kept


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
    quote = str(evidence.get("quote") or "").strip()[:2000]
    reasoning = str(evidence.get("critique_and_reasoning") or "").strip()[:2000]
    suggestion = str(entry.get("suggestion") or "").strip()[:2000]
    if not reasoning or (severity is not Severity.none and not suggestion):
        logger.warning("reviewer %s: dropping finding without explanation/action", dimension.value)
        return None
    if quote and (
        not _text_key(quote)
        or _text_key(quote) not in _text_key(" ".join(s.text for s in segments))
    ):
        logger.warning("reviewer %s: dropping finding with ungrounded quote", dimension.value)
        return None

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
            quote=quote,
            critique_and_reasoning=reasoning,
        ),
        suggestion=suggestion if severity is not Severity.none else "",
        citations=citations,
    )


def _segment_by_id(segment_id: Any, segments: Sequence[SegmentRef]) -> SegmentRef | None:
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

    async def review(self, context: ReviewContext, *, reviewer_run_id: str = "") -> ReviewResult:
        system = build_system_prompt(
            self.dimension,
            self.focus,
            visual_tools=self.visual_tools is not None,
            max_tool_calls=self.visual_tools.max_requests if self.visual_tools else 0,
            clip_window_seconds=(self.visual_tools.window_seconds if self.visual_tools else 5),
            grounding=self.grounding,
        )
        user = build_user_prompt(context, self.dimension)
        schema = findings_schema(self.finding_types, grounded=self.grounding)
        media = tuple(frame.media for frame in context.sampled_frames)
        records = [
            ToolCallRecord(
                tool="extract_frame",
                timestamp_ms=frame.timestamp_ms,
                label=f"Shared sample: {frame.media.label}",
                mime_type=frame.media.mime_type,
                content_path=frame.content_path,
            )
            for frame in context.sampled_frames
        ]

        if self.visual_tools is None:
            completion = await self.llm.complete_json(
                model=self.model,
                prompt_version=REVIEWER_PROMPT_VERSION,
                system=system,
                user=user,
                schema=schema,
                media=media,
                grounding=self.grounding,
            )
            return ReviewResult(
                findings=tuple(self._normalize(completion.data, context, reviewer_run_id)),
                usage=completion.usage,
                tool_calls=tuple(records),
                grounding=completion.grounding,
            )

        toolkit = self.visual_tools
        store = self.context_store
        # Distinct object indexes across chunks prevent a later chunk overwriting
        # footage already referenced by the same reviewer run.
        # Both toolkit functions return one media part per call.
        index = context.chunk_index * max(1, toolkit.max_requests)

        async def execute(name: str, arguments: dict[str, Any]) -> list[MediaPart]:
            nonlocal index
            try:
                parts = await toolkit.execute(name, arguments)
            except Exception as exc:  # noqa: BLE001 - provider handles the failed tool
                records.append(
                    ToolCallRecord(
                        tool=name,
                        timestamp_ms=_as_int(arguments.get("timestampMs")) or 0,
                        ok=False,
                        error=str(exc)[:300],
                    )
                )
                raise
            returned_media: list[MediaPart] = []
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
                returned_media.append(part)
                index += 1
            return returned_media

        completion = await self.llm.complete_json_with_tools(
            model=self.model,
            prompt_version=REVIEWER_PROMPT_VERSION,
            system=system,
            user=user,
            schema=schema,
            media=media,
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
        return [
            finding
            for finding in normalize_findings(
                raw,
                dimension=self.dimension,
                reviewer_run_id=reviewer_run_id,
                segments=context.segments,
                duration_ms=context.duration_ms,
            )
            if context.review_start_ms <= finding.startMs < context.review_end_ms
            and finding.endMs <= context.review_end_ms
        ]


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
