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

from app.agents.accessibility_agent import VisualAccessibilityReviewer
from app.agents.audience_agent import AudienceFitReviewer
from app.agents.brand_voice_agent import BrandVoiceReviewer
from app.agents.clarity_agent import ClarityReviewer
from app.agents.conversion_agent import ConversionCtaReviewer
from app.agents.cultural_agent import CulturalLocalizationReviewer
from app.agents.emotion_agent import EmotionalImpactReviewer
from app.agents.platform_agent import PlatformFitReviewer
from app.agents.retention_agent import EngagementRetentionReviewer
from app.agents.reviewer_base import LlmReviewer, ReviewContext, SegmentRef
from app.agents.safety_agent import LegalSafetyReviewer
from app.agents.seo_agent import SeoDiscoverabilityReviewer
from app.agents.structure_agent import StructurePacingReviewer
from app.agents.truth_agent import TruthEvidenceReviewer
from app.providers.base import LlmProvider, LlmUsage
from app.schemas.analysis import AnalysisDimension, Finding, ReviewerRunStatus

logger = logging.getLogger(__name__)

#: One reviewer class per dimension. Order follows `AnalysisDimension`.
REVIEWER_CLASSES: dict[AnalysisDimension, type[LlmReviewer]] = {
    AnalysisDimension.truth_evidence: TruthEvidenceReviewer,
    AnalysisDimension.clarity: ClarityReviewer,
    AnalysisDimension.structure_pacing: StructurePacingReviewer,
    AnalysisDimension.legal_safety: LegalSafetyReviewer,
    AnalysisDimension.cultural_localization: CulturalLocalizationReviewer,
    AnalysisDimension.platform_fit: PlatformFitReviewer,
    AnalysisDimension.audience_fit: AudienceFitReviewer,
    AnalysisDimension.brand_voice: BrandVoiceReviewer,
    AnalysisDimension.engagement_retention: EngagementRetentionReviewer,
    AnalysisDimension.emotional_impact: EmotionalImpactReviewer,
    AnalysisDimension.seo_discoverability: SeoDiscoverabilityReviewer,
    AnalysisDimension.visual_accessibility: VisualAccessibilityReviewer,
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
    started_at: datetime | None = None
    finished_at: datetime | None = None
    error: dict[str, Any] | None = None


def build_reviewers(
    llm: LlmProvider,
    *,
    model: str,
    dimensions: Sequence[AnalysisDimension],
) -> list[LlmReviewer]:
    """Instantiate one reviewer per dimension, in canonical order."""
    reviewers: list[LlmReviewer] = []
    for dimension in dimensions:
        reviewer_class = REVIEWER_CLASSES.get(dimension)
        if reviewer_class is None:  # pragma: no cover - enum is exhaustive
            logger.warning("no reviewer registered for %s; skipping", dimension)
            continue
        reviewers.append(reviewer_class(llm, model=model))
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
) -> list[ReviewContext]:
    return [
        ReviewContext(
            persona=persona,
            platform=platform,
            audience=audience,
            language=language,
            duration_ms=duration_ms,
            segments=chunk.segments,
            context_segments=chunk.context_segments,
        )
        for chunk in chunks
    ]


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
    failures: list[str] = []
    successes = 0

    for context in contexts:
        async with semaphore:
            try:
                result = await reviewer.review(
                    context, reviewer_run_id=reviewer_run_id
                )
            except Exception as exc:  # noqa: BLE001 - one reviewer must not sink the run
                logger.exception("%s: chunk failed", reviewer.dimension.value)
                failures.append(f"{type(exc).__name__}: {exc}")
                continue
        successes += 1
        segment_count += len(context.segments)
        usage = add_usage(usage, result.usage)
        window_start = context.segments[0].start_ms
        window_end = context.segments[-1].end_ms
        findings.extend(
            clip_findings_to_window(
                result.findings, start_ms=window_start, end_ms=window_end
            )
        )

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
        started_at=started_at,
        finished_at=finished_at,
        error=(
            {"code": "REVIEWER_PARTIAL", "message": "; ".join(failures)[:500]}
            if failures
            else None
        ),
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
