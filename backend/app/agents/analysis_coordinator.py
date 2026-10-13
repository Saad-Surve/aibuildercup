"""Analysis coordinator: chunk the transcript and fan out the reviewers.

Tier 1 of `docs/technical-design/backend-plan.md` section 8. Running every reviewer
over every segment is unbounded cost, so the transcript is cut into roughly 8-12k
token windows and each reviewer makes one structured call per window. Concurrency is
capped by a semaphore; failures are isolated per dimension so one broken reviewer
never hides the others' results.

This module owns the fan-out. Persistence lives in `AnalysisService`, and the job
lifecycle lives in `app/workers/analysis_worker.py`.
"""

import asyncio
import logging
import time
from collections.abc import Awaitable, Callable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from app.agents.audience_brand_agent import AudienceBrandReviewer
from app.agents.clarity_agent import ClarityReviewer
from app.agents.conversion_agent import ConversionCtaReviewer
from app.agents.cultural_agent import CulturalLocalizationReviewer
from app.agents.emotion_agent import EmotionalImpactReviewer
from app.agents.pacing_agent import PacingRetentionReviewer
from app.agents.platform_agent import PlatformFitReviewer
from app.agents.reviewer_base import (
    LlmReviewer,
    ReviewContext,
    SegmentRef,
    ToolCallRecord,
    deduplicate_findings,
)
from app.agents.safety_agent import LegalSafetyReviewer
from app.agents.truth_agent import TruthEvidenceReviewer
from app.providers.base import LlmProvider, LlmUsage
from app.schemas.analysis import AnalysisDimension, Finding, ReviewerRunStatus
from app.services.video_tools import ContextArtifactStore, MediaToolkit

logger = logging.getLogger(__name__)

#: One reviewer class per active dimension. Order follows `AnalysisDimension`.
REVIEWER_CLASSES: dict[AnalysisDimension, type[LlmReviewer]] = {
    AnalysisDimension.truth_evidence: TruthEvidenceReviewer,
    AnalysisDimension.clarity: ClarityReviewer,
    AnalysisDimension.pacing_retention: PacingRetentionReviewer,
    AnalysisDimension.legal_safety: LegalSafetyReviewer,
    AnalysisDimension.cultural_localization: CulturalLocalizationReviewer,
    AnalysisDimension.platform_fit: PlatformFitReviewer,
    AnalysisDimension.audience_brand: AudienceBrandReviewer,
    AnalysisDimension.emotional_impact: EmotionalImpactReviewer,
    AnalysisDimension.conversion_cta: ConversionCtaReviewer,
}

#: ~9k tokens at four characters per token, the middle of the 8-12k window.
DEFAULT_CHUNK_CHARS = 36_000

#: Neighbouring segments shown as context but never reported on.
CONTEXT_SEGMENT_COUNT = 2


@dataclass(frozen=True)
class TranscriptChunk:
    """A contiguous window of the transcript that one reviewer call covers."""

    index: int
    segments: tuple[SegmentRef, ...]
    context_segments: tuple[SegmentRef, ...]
    start_ms: int
    end_ms: int


@dataclass
class DimensionOutcome:
    """Everything one reviewer produced across all of its chunks."""

    dimension: AnalysisDimension
    reviewer_run_id: str
    status: ReviewerRunStatus
    findings: list[Finding] = field(default_factory=list)
    usage: LlmUsage = field(default_factory=LlmUsage)
    model: str | None = None
    input_segment_count: int = 0
    duration_ms: int = 0
    #: Frames/clips the reviewer pulled in through the footage tools.
    tool_calls: list[ToolCallRecord] = field(default_factory=list)
    #: Web grounding: search queries and sources (title/url), when the reviewer searched.
    grounding_queries: list[str] = field(default_factory=list)
    grounding_sources: list[dict[str, Any]] = field(default_factory=list)
    grounding_html: str = ""
    started_at: datetime | None = None
    finished_at: datetime | None = None
    error: dict[str, Any] | None = None
    #: Review windows (start_ms, end_ms) of the chunks this reviewer finished. Time inside
    #: them with no finding was read and had nothing to flag.
    reviewed_spans: list[tuple[int, int]] = field(default_factory=list)


def build_reviewers(
    llm: LlmProvider,
    *,
    model: str,
    dimensions: Sequence[AnalysisDimension],
    visual_tools: MediaToolkit | None = None,
    context_store: ContextArtifactStore | None = None,
    grounding_enabled: bool = False,
) -> list[LlmReviewer]:
    """Instantiate one reviewer per dimension, in canonical order.

    `visual_tools` and `context_store` (when supplied) are shared by every reviewer: the
    toolkit is stateless apart from the source video, and the store writes under the run.
    `grounding_enabled` is passed to every reviewer, but only the ones that declare
    `supports_grounding` actually search.
    """
    reviewers: list[LlmReviewer] = []
    for dimension in dimensions:
        reviewer_class = REVIEWER_CLASSES.get(dimension)
        if reviewer_class is None:  # pragma: no cover - enum is exhaustive
            logger.warning("no reviewer registered for %s; skipping", dimension)
            continue
        reviewers.append(
            reviewer_class(
                llm,
                model=model,
                visual_tools=visual_tools,
                context_store=context_store,
                grounding_enabled=grounding_enabled,
            )
        )
    return reviewers


def chunk_segments(
    segments: Sequence[SegmentRef],
    *,
    max_chars: int = DEFAULT_CHUNK_CHARS,
    context_count: int = CONTEXT_SEGMENT_COUNT,
) -> list[TranscriptChunk]:
    """Partition segments into windows of at most `max_chars` characters.

    The partition is strict - every segment is owned by exactly one chunk - so a
    finding can never be produced twice. Neighbouring segments ride along as
    context only, which keeps the reviewer oriented without duplicating work.
    """
    if max_chars <= 0:
        raise ValueError("max_chars must be positive")
    if not segments:
        return []

    # Strict partition: each segment belongs to exactly one group, tracked as index
    # ranges so identical-looking segments cannot be confused by `list.index`.
    ranges: list[tuple[int, int]] = []
    current_start = 0
    current_chars = 0
    for position, segment in enumerate(segments):
        size = _segment_chars(segment)
        if position > current_start and current_chars + size > max_chars:
            ranges.append((current_start, position))
            current_start = position
            current_chars = 0
        current_chars += size
    if current_start < len(segments):
        ranges.append((current_start, len(segments)))

    chunks: list[TranscriptChunk] = []
    for index, (first, last) in enumerate(ranges):
        group = segments[first:last]
        before = segments[max(0, first - context_count) : first]
        after = segments[last : last + context_count]
        chunks.append(
            TranscriptChunk(
                index=index,
                segments=tuple(group),
                context_segments=tuple(before) + tuple(after),
                start_ms=group[0].start_ms,
                end_ms=group[-1].end_ms,
            )
        )
    return chunks


def _segment_chars(segment: SegmentRef) -> int:
    # The prompt prints `id|start|end: text` for each segment; account for that too.
    return len(segment.text) + len(segment.segment_id) + 32


def build_review_contexts(
    chunks: Sequence[TranscriptChunk],
    *,
    persona: str,
    platform: str,
    audience: str,
    language: str,
    duration_ms: int,
    video_title: str = "",
    thumbnail_concept: str = "",
    project_brief: str = "",
) -> list[ReviewContext]:
    continuity = _video_continuity(chunks) if len(chunks) > 1 else ""
    return [
        ReviewContext(
            persona=persona,
            platform=platform,
            audience=audience,
            language=language,
            duration_ms=duration_ms,
            segments=chunk.segments,
            context_segments=chunk.context_segments,
            video_title=video_title,
            thumbnail_concept=thumbnail_concept,
            project_brief=project_brief,
            video_context=continuity,
            chunk_index=index,
            window_start_ms=0 if index == 0 else chunk.start_ms,
            window_end_ms=(chunks[index + 1].start_ms if index + 1 < len(chunks) else duration_ms),
        )
        for index, chunk in enumerate(chunks)
    ]


def _video_continuity(chunks: Sequence[TranscriptChunk]) -> str:
    """Bounded real excerpts keep distant hooks/payoffs in view without another LLM call."""
    segments = [segment for chunk in chunks for segment in chunk.segments]
    indexes = set(range(min(4, len(segments))))
    indexes.update(range(max(0, len(segments) - 4), len(segments)))
    indexes.update(round(i * (len(segments) - 1) / 15) for i in range(16))
    lines = [
        "Opening, ending, and selected excerpts across the video, not the full transcript. "
        "Use them to connect ideas; omitted text may contain a payoff or explanation. "
        "Do not claim something is absent from the entire video based on these excerpts."
    ]
    for index in sorted(indexes):
        segment = segments[index]
        text = segment.text[:280]
        suffix = " [excerpt truncated]" if len(segment.text) > 280 else ""
        lines.append(f"{segment.start_ms} -> {segment.end_ms}: {text}{suffix}")
    return "\n".join(lines)


def clip_findings_to_window(
    findings: Sequence[Finding], *, start_ms: int, end_ms: int
) -> list[Finding]:
    """Keep findings that start inside the window this chunk owns.

    The reviewer is shown neighbouring segments as context and can still report on
    them; those belong to the chunk that owns that time, not this one.
    """
    return [finding for finding in findings if start_ms <= finding.startMs < end_ms]


def add_usage(left: LlmUsage, right: LlmUsage) -> LlmUsage:
    return LlmUsage(
        input_tokens=left.input_tokens + right.input_tokens,
        output_tokens=left.output_tokens + right.output_tokens,
    )


async def run_dimension(
    reviewer: LlmReviewer,
    contexts: Sequence[ReviewContext],
    *,
    semaphore: asyncio.Semaphore,
    reviewer_run_id: str,
) -> DimensionOutcome:
    """Run one reviewer over every chunk, serially within the dimension.

    Chunk calls for a dimension run one at a time so its findings arrive in
    transcript order; the semaphore is what caps work across dimensions. A chunk
    that fails is recorded and the rest still run, so partial results survive.
    """
    started_at = datetime.now(UTC)
    started = time.monotonic()
    findings: list[Finding] = []
    usage = LlmUsage()
    segment_count = 0
    tool_calls: list[ToolCallRecord] = []
    grounding_queries: list[str] = []
    grounding_sources: list[dict[str, Any]] = []
    grounding_html = ""
    failures: list[str] = []
    successes = 0
    reviewed_spans: list[tuple[int, int]] = []

    for context in contexts:
        async with semaphore:
            try:
                result = await reviewer.review(context, reviewer_run_id=reviewer_run_id)
            except Exception as exc:  # noqa: BLE001 - one reviewer must not sink the run
                logger.exception("%s: chunk failed", reviewer.dimension.value)
                failures.append(f"{type(exc).__name__}: {exc}")
                continue
        successes += 1
        segment_count += len(context.segments)
        tool_calls.extend(result.tool_calls)
        if result.grounding is not None:
            for query in result.grounding.queries:
                if query not in grounding_queries:
                    grounding_queries.append(query)
            seen_urls = {source.get("url") for source in grounding_sources}
            for source in result.grounding.sources:
                url = source.uri or ""
                if url and url in seen_urls:
                    continue
                grounding_sources.append(
                    {
                        "title": source.title or source.domain or url,
                        "url": url,
                        "domain": source.domain,
                    }
                )
                seen_urls.add(url)
            grounding_html = grounding_html or result.grounding.search_suggestions_html
        usage = add_usage(usage, result.usage)
        window_start = context.review_start_ms
        window_end = context.review_end_ms
        reviewed_spans.append((window_start, window_end))
        findings.extend(
            clip_findings_to_window(result.findings, start_ms=window_start, end_ms=window_end)
        )

    findings = deduplicate_findings(findings)

    # Grounding metadata can come back empty in JSON mode, so fold the sources the model
    # cited on its findings into the aggregate list the UI shows.
    seen_urls = {source.get("url") for source in grounding_sources}
    for finding in findings:
        for citation in finding.citations:
            if not isinstance(citation, dict):
                continue
            url = str(citation.get("url") or "").strip()
            if not url or url in seen_urls:
                continue
            grounding_sources.append(
                {"title": str(citation.get("title") or url), "url": url, "domain": ""}
            )
            seen_urls.add(url)

    finished_at = datetime.now(UTC)
    duration_ms = int((time.monotonic() - started) * 1000)
    if successes == 0:
        return DimensionOutcome(
            dimension=reviewer.dimension,
            reviewer_run_id=reviewer_run_id,
            status=ReviewerRunStatus.failed,
            findings=findings,
            usage=usage,
            model=getattr(reviewer, "model", None),
            input_segment_count=segment_count,
            duration_ms=duration_ms,
            tool_calls=tool_calls,
            grounding_queries=grounding_queries,
            grounding_sources=grounding_sources,
            grounding_html=grounding_html,
            started_at=started_at,
            finished_at=finished_at,
            error={"code": "REVIEWER_FAILED", "message": "; ".join(failures)[:500]},
        )
    return DimensionOutcome(
        dimension=reviewer.dimension,
        reviewer_run_id=reviewer_run_id,
        status=ReviewerRunStatus.succeeded,
        findings=findings,
        usage=usage,
        model=getattr(reviewer, "model", None),
        input_segment_count=segment_count,
        duration_ms=duration_ms,
        tool_calls=tool_calls,
        grounding_queries=grounding_queries,
        grounding_sources=grounding_sources,
        grounding_html=grounding_html,
        started_at=started_at,
        finished_at=finished_at,
        error=(
            {"code": "REVIEWER_PARTIAL", "message": "; ".join(failures)[:500]} if failures else None
        ),
        reviewed_spans=reviewed_spans,
    )


async def run_reviewers(
    reviewers: Sequence[LlmReviewer],
    contexts: Sequence[ReviewContext],
    *,
    max_concurrency: int,
    reviewer_run_ids: Mapping[AnalysisDimension, str],
    on_outcome: Callable[[DimensionOutcome], Awaitable[None]] | None = None,
) -> list[DimensionOutcome]:
    """Fan every reviewer out over every chunk, bounded by `max_concurrency`.

    `reviewer_run_ids` supplies the document ids created with the run, so results land
    on the queued placeholders. `on_outcome` is awaited as each dimension finishes, so
    callers can persist partial results and report progress while others still run.
    Returns one outcome per reviewer, in the order the reviewers were given.
    """
    if not contexts:
        return []

    missing = [r.dimension.value for r in reviewers if r.dimension not in reviewer_run_ids]
    if missing:
        raise KeyError(f"missing reviewer run ids for: {', '.join(missing)}")

    semaphore = asyncio.Semaphore(max(1, max_concurrency))

    async def run_and_report(reviewer: LlmReviewer) -> DimensionOutcome:
        outcome = await run_dimension(
            reviewer,
            contexts,
            semaphore=semaphore,
            reviewer_run_id=reviewer_run_ids[reviewer.dimension],
        )
        if on_outcome is not None:
            await on_outcome(outcome)
        return outcome

    return list(await asyncio.gather(*(run_and_report(reviewer) for reviewer in reviewers)))


__all__ = [
    "CONTEXT_SEGMENT_COUNT",
    "DEFAULT_CHUNK_CHARS",
    "DimensionOutcome",
    "REVIEWER_CLASSES",
    "TranscriptChunk",
    "add_usage",
    "build_review_contexts",
    "build_reviewers",
    "chunk_segments",
    "clip_findings_to_window",
    "run_dimension",
    "run_reviewers",
]
