"""Analysis coordinator tests: chunking and bounded fan-out."""

import asyncio

import pytest

from app.agents.analysis_coordinator import (
    DEFAULT_CHUNK_CHARS,
    DimensionOutcome,
    build_review_contexts,
    build_reviewers,
    chunk_segments,
    clip_findings_to_window,
    run_dimension,
    run_reviewers,
)
from app.agents.reviewer_base import LlmReviewer, ReviewContext, ReviewResult, SegmentRef
from app.providers.base import LlmUsage
from app.schemas.analysis import (
    CORE_DIMENSIONS,
    AnalysisDimension,
    Finding,
    FindingEvidence,
    ReviewerRunStatus,
    resolve_dimensions,
)


def seg(index: int, start: int, end: int, text: str = "hello") -> SegmentRef:
    return SegmentRef(f"seg-{index}", start, end, text)


def make_findings(dimension: AnalysisDimension, *spans: tuple[int, int]) -> list[Finding]:
    return [
        Finding(
            findingId=f"f-{dimension.value}-{start}",
            dimension=dimension,
            reviewerRunId="rev",
            segmentId="seg-1",
            startMs=start,
            endMs=end,
            score=7.0,
            confidence=0.5,
            severity="low",
            findingType="t",
            evidence=FindingEvidence(quote="q", explanation="e"),
            suggestion="s",
        )
        for start, end in spans
    ]


# --- chunking ---------------------------------------------------------------


def test_short_transcript_is_one_chunk() -> None:
    chunks = chunk_segments([seg(1, 0, 1000), seg(2, 1000, 2000)])
    assert len(chunks) == 1
    assert chunks[0].index == 0
    assert [s.segment_id for s in chunks[0].segments] == ["seg-1", "seg-2"]
    assert chunks[0].context_segments == ()
    assert (chunks[0].start_ms, chunks[0].end_ms) == (0, 2000)


def test_chunks_partition_segments_without_overlap() -> None:
    segments = [seg(i, i * 1000, (i + 1) * 1000, "x" * 50) for i in range(10)]
    chunks = chunk_segments(segments, max_chars=200)
    assert len(chunks) > 1
    owned = [s.segment_id for chunk in chunks for s in chunk.segments]
    assert owned == [s.segment_id for s in segments]
    assert len(set(owned)) == len(owned)


def test_neighbouring_segments_ride_along_as_context_only() -> None:
    segments = [seg(i, i * 1000, (i + 1) * 1000, "x" * 100) for i in range(8)]
    chunks = chunk_segments(segments, max_chars=250, context_count=2)
    assert len(chunks) >= 2
    second = chunks[1]
    # Context is segments from the neighbouring chunks, never its own.
    context_ids = {s.segment_id for s in second.context_segments}
    owned_ids = {s.segment_id for s in second.segments}
    assert context_ids
    assert not context_ids & owned_ids
    assert chunks[0].segments[-1].segment_id in context_ids


def test_oversized_segment_still_becomes_its_own_chunk() -> None:
    segments = [seg(1, 0, 1000, "y" * 10_000), seg(2, 1000, 2000, "short")]
    chunks = chunk_segments(segments, max_chars=100)
    assert len(chunks) == 2
    assert [s.segment_id for s in chunks[0].segments] == ["seg-1"]
    assert [s.segment_id for s in chunks[1].segments] == ["seg-2"]


def test_empty_segments_produce_no_chunks() -> None:
    assert chunk_segments([]) == []


def test_chunking_rejects_a_non_positive_window() -> None:
    with pytest.raises(ValueError, match="max_chars"):
        chunk_segments([seg(1, 0, 1)], max_chars=0)


def test_default_chunk_window_is_about_nine_thousand_tokens() -> None:
    # Roughly four characters per token, at the middle of the design's 8-12k window.
    assert 8_000 * 4 <= DEFAULT_CHUNK_CHARS <= 12_000 * 4


def test_contexts_carry_the_shared_creator_context() -> None:
    chunks = chunk_segments([seg(1, 0, 1000)])
    contexts = build_review_contexts(
        chunks,
        persona="persona",
        platform="youtube",
        audience="engineers",
        language="en",
        duration_ms=1000,
    )
    assert len(contexts) == 1
    assert contexts[0].persona == "persona"
    assert contexts[0].platform == "youtube"
    assert contexts[0].audience == "engineers"
    assert contexts[0].language == "en"
    assert contexts[0].duration_ms == 1000


# --- clipping ---------------------------------------------------------------


def test_clip_findings_to_window_drops_neighbour_reports() -> None:
    findings = make_findings(AnalysisDimension.clarity, (0, 100), (500, 600), (2000, 2100))
    kept = clip_findings_to_window(findings, start_ms=0, end_ms=1000)
    assert [(f.startMs, f.endMs) for f in kept] == [(0, 100), (500, 600)]


def test_clip_findings_uses_start_not_end() -> None:
    # A finding that begins inside the window is owned here even if it runs past it.
    findings = make_findings(AnalysisDimension.clarity, (900, 1500))
    assert clip_findings_to_window(findings, start_ms=0, end_ms=1000) == findings
    assert clip_findings_to_window(findings, start_ms=1000, end_ms=2000) == []


# --- registry ---------------------------------------------------------------


def test_every_dimension_has_a_reviewer() -> None:
    from app.agents.analysis_coordinator import REVIEWER_CLASSES

    assert set(REVIEWER_CLASSES) == set(AnalysisDimension)


def test_core_dimensions_are_always_in_the_run() -> None:
    assert resolve_dimensions([]) == list(CORE_DIMENSIONS)
    extended = resolve_dimensions([AnalysisDimension.conversion_cta])
    assert list(CORE_DIMENSIONS) == extended[: len(CORE_DIMENSIONS)]
    assert extended[-1] is AnalysisDimension.conversion_cta
    # Requesting a core dimension twice does not duplicate it.
    assert resolve_dimensions([AnalysisDimension.clarity]) == list(CORE_DIMENSIONS)


def test_build_reviewers_instantiates_one_per_dimension() -> None:
    class _Llm:
        pass

    reviewers = build_reviewers(_Llm(), model="m", dimensions=list(AnalysisDimension))
    assert len(reviewers) == len(AnalysisDimension)
    assert {r.dimension for r in reviewers} == set(AnalysisDimension)


def test_build_reviewers_respects_the_requested_subset() -> None:
    class _Llm:
        pass

    reviewers = build_reviewers(
        _Llm(),
        model="m",
        dimensions=[AnalysisDimension.clarity, AnalysisDimension.legal_safety],
    )
    assert [r.dimension for r in reviewers] == [
        AnalysisDimension.clarity,
        AnalysisDimension.legal_safety,
    ]


# --- fan-out ----------------------------------------------------------------


class _ScriptedReviewer(LlmReviewer):
    """Reviewer whose answer (or failure) is scripted per instance."""

    focus = "test"

    def __init__(
        self,
        responses: list[dict | Exception],
        *,
        dimension: AnalysisDimension = AnalysisDimension.clarity,
    ) -> None:
        self.dimension = dimension
        self.responses = list(responses)
        self.calls = 0
        self.concurrent = 0
        self.max_concurrent = 0

    async def review(self, context, *, reviewer_run_id: str = "") -> ReviewResult:
        self.calls += 1
        self.concurrent += 1
        self.max_concurrent = max(self.max_concurrent, self.concurrent)
        await asyncio.sleep(0)  # let other tasks interleave
        self.concurrent -= 1
        if not self.responses:
            return ReviewResult(findings=(), usage=LlmUsage(1, 1))
        answer = self.responses.pop(0)
        if isinstance(answer, Exception):
            raise answer
        return ReviewResult(
            findings=tuple(make_findings(self.dimension, (0, 10))), usage=LlmUsage(2, 3)
        )


def _context() -> ReviewContext:
    return ReviewContext(
        persona="",
        platform="youtube",
        audience="",
        language="en",
        duration_ms=100,
        segments=(seg(1, 0, 100),),
    )


async def test_run_dimension_succeeds_and_stamps_the_given_id() -> None:
    reviewer = _ScriptedReviewer([{}])
    outcome = await run_dimension(
        reviewer, [_context()], semaphore=asyncio.Semaphore(4), reviewer_run_id="rev-fixed"
    )
    assert outcome.reviewer_run_id == "rev-fixed"
    assert outcome.status is ReviewerRunStatus.succeeded
    assert outcome.input_segment_count == 1
    assert len(outcome.findings) == 1
    assert outcome.usage == LlmUsage(2, 3)
    assert outcome.started_at is not None and outcome.finished_at is not None


async def test_run_dimension_reports_failure_when_every_chunk_raises() -> None:
    reviewer = _ScriptedReviewer([RuntimeError("boom"), ValueError("bang")])
    outcome = await run_dimension(
        reviewer,
        [_context(), _context()],
        semaphore=asyncio.Semaphore(4),
        reviewer_run_id="rev-1",
    )
    assert outcome.status is ReviewerRunStatus.failed
    assert outcome.findings == []
    assert outcome.error is not None
    assert outcome.error["code"] == "REVIEWER_FAILED"
    assert "boom" in outcome.error["message"]


async def test_run_dimension_keeps_partial_results() -> None:
    reviewer = _ScriptedReviewer([{}, RuntimeError("mid")])
    outcome = await run_dimension(
        reviewer,
        [_context(), _context()],
        semaphore=asyncio.Semaphore(4),
        reviewer_run_id="rev-1",
    )
    assert outcome.status is ReviewerRunStatus.succeeded
    assert len(outcome.findings) == 1
    assert outcome.error is not None
    assert outcome.error["code"] == "REVIEWER_PARTIAL"


async def test_run_reviewers_bounds_concurrency() -> None:
    dimensions = list(AnalysisDimension)[:6]
    reviewers = [
        _ScriptedReviewer([{}], dimension=dimension) for dimension in dimensions
    ]
    outcomes = await run_reviewers(
        reviewers,
        [_context()],
        max_concurrency=2,
        reviewer_run_ids={reviewer.dimension: f"rev-{i}" for i, reviewer in enumerate(reviewers)},
    )
    assert len(outcomes) == 6
    assert max(r.max_concurrent for r in reviewers) <= 2
    assert {o.dimension for o in outcomes} == set(dimensions)


async def test_run_reviewers_reports_outcomes_as_they_land() -> None:
    seen: list[str] = []

    async def on_outcome(outcome: DimensionOutcome) -> None:
        seen.append(outcome.reviewer_run_id)

    dimensions = list(AnalysisDimension)[:3]
    reviewers = [
        _ScriptedReviewer([{}], dimension=dimension) for dimension in dimensions
    ]
    run_ids = {dimension: f"rev-{dimension.value}" for dimension in dimensions}
    outcomes = await run_reviewers(
        reviewers,
        [_context()],
        max_concurrency=3,
        reviewer_run_ids=run_ids,
        on_outcome=on_outcome,
    )
    assert sorted(seen) == sorted(o.reviewer_run_id for o in outcomes)
    assert len(seen) == 3


async def test_run_reviewers_requires_an_id_per_reviewer() -> None:
    reviewers = [_ScriptedReviewer([{}])]
    with pytest.raises(KeyError, match="missing reviewer run ids"):
        await run_reviewers(
            reviewers,
            [_context()],
            max_concurrency=1,
            reviewer_run_ids={},
        )


async def test_run_reviewers_with_no_contexts_does_nothing() -> None:
    assert (
        await run_reviewers(
            [_ScriptedReviewer([{}])],
            [],
            max_concurrency=1,
            reviewer_run_ids={AnalysisDimension.clarity: "rev-1"},
        )
        == []
    )


def test_dimension_outcome_defaults() -> None:
    outcome = DimensionOutcome(
        dimension=AnalysisDimension.clarity,
        reviewer_run_id="rev-1",
        status=ReviewerRunStatus.queued,
    )
    assert outcome.findings == []
    assert outcome.usage == LlmUsage(0, 0)
    assert outcome.error is None
