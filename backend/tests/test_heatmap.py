"""Heatmap aggregation tests.

These pin the aggregation rules in `docs/technical-design/backend-plan.md` §9:
clamping, fixed bins, weighted scores, preserved finding ids, and colors.
"""

from app.schemas.analysis import (
    AnalysisDimension,
    Finding,
    FindingEvidence,
    HeatmapColor,
    Severity,
    max_severity,
)
from app.services.heatmap import (
    BIN_MS,
    aggregate_bins,
    bin_id_for,
    color_for,
    normalize_span,
    summarize_findings,
    worst_severity,
)

DIM = AnalysisDimension.clarity
OTHER = AnalysisDimension.truth_evidence


def make_finding(
    finding_id: str,
    *,
    dimension: AnalysisDimension = DIM,
    start_ms: int = 0,
    end_ms: int = 1000,
    score: float = 7.0,
    severity: Severity = Severity.medium,
) -> Finding:
    return Finding(
        findingId=finding_id,
        dimension=dimension,
        reviewerRunId="rev-1",
        segmentId="seg-1",
        startMs=start_ms,
        endMs=end_ms,
        score=score,
        confidence=0.8,
        severity=severity,
        findingType="test",
        evidence=FindingEvidence(quote="q", explanation="e"),
        suggestion="s",
    )


# --- color_for ---------------------------------------------------------------


def test_color_score_bands() -> None:
    assert color_for(8.0, Severity.none) is HeatmapColor.green
    assert color_for(7.99, Severity.low) is HeatmapColor.yellow
    assert color_for(6.0, Severity.medium) is HeatmapColor.yellow
    assert color_for(5.99, Severity.high) is HeatmapColor.orange
    assert color_for(4.0, Severity.low) is HeatmapColor.orange
    assert color_for(3.99, Severity.none) is HeatmapColor.red
    assert color_for(0.0, Severity.high) is HeatmapColor.red


def test_color_critical_is_red_regardless_of_score() -> None:
    assert color_for(9.5, Severity.critical) is HeatmapColor.red
    assert color_for(8.0, Severity.critical) is HeatmapColor.red


# --- normalize_span ---------------------------------------------------------


def test_normalize_span_clamps_to_duration() -> None:
    assert normalize_span(-500, 12_000, duration_ms=10_000) == (0, 10_000)
    assert normalize_span(2_000, 9_000, duration_ms=10_000) == (2_000, 9_000)


def test_normalize_span_expands_point_findings() -> None:
    assert normalize_span(1_000, 1_000, duration_ms=10_000) == (1_000, 1_001)
    assert normalize_span(5_000, 4_000, duration_ms=10_000) == (5_000, 5_001)


def test_normalize_span_drops_findings_past_the_end() -> None:
    assert normalize_span(10_000, 12_000, duration_ms=10_000) is None
    assert normalize_span(12_000, 12_000, duration_ms=10_000) is None


# --- aggregate_bins ---------------------------------------------------------


def test_empty_inputs_produce_no_bins() -> None:
    assert aggregate_bins([], duration_ms=60_000) == []
    assert aggregate_bins([make_finding("f1")], duration_ms=0) == []


def test_finding_lands_in_its_bin() -> None:
    bins = aggregate_bins([make_finding("f1", start_ms=0, end_ms=1_000)], duration_ms=20_000)
    assert len(bins) == 1
    bin = bins[0]
    assert bin.binId == "clarity-0"
    assert (bin.startMs, bin.endMs) == (0, BIN_MS)
    assert bin.score == 7.0
    assert bin.findingIds == ["f1"]
    assert bin.severity is Severity.medium


def test_bin_id_is_dimension_and_start() -> None:
    assert bin_id_for(DIM, 40_000) == "clarity-40000"
    assert bin_id_for(OTHER, 0) == "truth_evidence-0"


def test_bins_are_fixed_width_and_ordered() -> None:
    findings = [
        make_finding("late", start_ms=12_000, end_ms=13_000),
        make_finding("early", start_ms=1_000, end_ms=2_000),
    ]
    bins = aggregate_bins(findings, duration_ms=20_000)
    assert [(b.startMs, b.endMs) for b in bins] == [(0, 5_000), (10_000, 15_000)]
    assert [b.findingIds for b in bins] == [["early"], ["late"]]


def test_dimensions_get_separate_tracks() -> None:
    findings = [
        make_finding("a", dimension=DIM, start_ms=0, end_ms=1_000),
        make_finding("b", dimension=OTHER, start_ms=0, end_ms=1_000),
    ]
    bins = aggregate_bins(findings, duration_ms=20_000)
    assert [(b.dimension, b.findingIds) for b in bins] == [
        (AnalysisDimension.truth_evidence, ["b"]),
        (DIM, ["a"]),
    ]


def test_long_finding_spans_several_bins() -> None:
    bins = aggregate_bins(
        [make_finding("long", start_ms=0, end_ms=15_000, score=8.0)],
        duration_ms=20_000,
    )
    assert [b.binId for b in bins] == ["clarity-0", "clarity-5000", "clarity-10000"]
    assert all(b.score == 8.0 for b in bins)
    assert all(b.findingIds == ["long"] for b in bins)


def test_overlapping_findings_average_by_overlap() -> None:
    # Bin [0, 5000): f1 covers all 5000ms at 10.0, f2 covers the first 1000ms at 0.0.
    # Weighted mean = (10*5000 + 0*1000) / 6000 = 8.333.. -> 8.33
    findings = [
        make_finding("f1", start_ms=0, end_ms=5_000, score=10.0, severity=Severity.none),
        make_finding("f2", start_ms=0, end_ms=1_000, score=0.0, severity=Severity.high),
    ]
    bins = aggregate_bins(findings, duration_ms=10_000)
    assert len(bins) == 1
    assert bins[0].score == 8.33
    assert sorted(bins[0].findingIds) == ["f1", "f2"]


def test_bin_severity_is_the_worst_of_its_findings() -> None:
    findings = [
        make_finding("ok", start_ms=0, end_ms=5_000, score=9.0, severity=Severity.none),
        make_finding("bad", start_ms=1_000, end_ms=2_000, score=3.0, severity=Severity.critical),
    ]
    bins = aggregate_bins(findings, duration_ms=10_000)
    assert bins[0].severity is Severity.critical
    assert bins[0].color is HeatmapColor.red


def test_critical_reddens_a_high_scoring_bin() -> None:
    findings = [
        make_finding("a", start_ms=0, end_ms=5_000, score=9.5, severity=Severity.critical),
    ]
    bins = aggregate_bins(findings, duration_ms=10_000)
    assert bins[0].score == 9.5
    assert bins[0].color is HeatmapColor.red


def test_findings_outside_the_duration_are_clamped_or_dropped() -> None:
    findings = [
        make_finding("overhang", start_ms=8_000, end_ms=20_000, score=5.0),
        make_finding("past", start_ms=30_000, end_ms=31_000),
    ]
    bins = aggregate_bins(findings, duration_ms=10_000)
    assert [b.binId for b in bins] == ["clarity-5000"]
    assert bins[0].score == 5.0


def test_duplicate_finding_ids_are_recorded_once() -> None:
    findings = [
        make_finding("dup", start_ms=0, end_ms=2_000),
        make_finding("dup", start_ms=2_000, end_ms=4_000),
    ]
    bins = aggregate_bins(findings, duration_ms=10_000)
    assert bins[0].findingIds == ["dup"]


def test_custom_bin_width() -> None:
    bins = aggregate_bins(
        [make_finding("f", start_ms=0, end_ms=10_000, score=6.0)],
        duration_ms=10_000,
        bin_ms=1_000,
    )
    assert len(bins) == 10
    assert bins[0].startMs == 0
    assert bins[-1].endMs == 10_000


def test_zero_or_negative_bin_width_is_rejected() -> None:
    try:
        aggregate_bins([make_finding("f")], duration_ms=10_000, bin_ms=0)
    except ValueError as exc:
        assert "bin_ms" in str(exc)
    else:  # pragma: no cover - the call must raise
        raise AssertionError("expected ValueError")


# --- summarize_findings -----------------------------------------------------


def test_summarize_counts_every_severity() -> None:
    findings = [
        make_finding("a", severity=Severity.none),
        make_finding("b", severity=Severity.none),
        make_finding("c", severity=Severity.low),
        make_finding("d", severity=Severity.high),
        make_finding("e", severity=Severity.critical),
    ]
    summary = summarize_findings(findings)
    assert summary.counts == {
        "none": 2,
        "low": 1,
        "medium": 0,
        "high": 1,
        "critical": 1,
    }


def test_summarize_scores_are_duration_weighted() -> None:
    findings = [
        make_finding("long", start_ms=0, end_ms=9_000, score=9.0),
        make_finding("short", start_ms=9_000, end_ms=10_000, score=1.0),
    ]
    summary = summarize_findings(findings)
    # (9*9000 + 1*1000) / 10000 = 8.2
    assert summary.score_by_dimension == {"clarity": 8.2}


def test_summarize_overall_is_the_mean_of_dimension_scores() -> None:
    findings = [
        make_finding("a", dimension=DIM, start_ms=0, end_ms=1_000, score=8.0),
        make_finding("b", dimension=OTHER, start_ms=0, end_ms=1_000, score=4.0),
    ]
    summary = summarize_findings(findings)
    assert summary.overall_score == 6.0
    assert summary.score_by_dimension == {"clarity": 8.0, "truth_evidence": 4.0}


def test_summarize_empty_findings() -> None:
    summary = summarize_findings([])
    assert summary.overall_score is None
    assert summary.score_by_dimension == {}
    assert summary.counts["critical"] == 0


# --- severity helpers -------------------------------------------------------


def test_max_severity_and_worst_severity() -> None:
    assert max_severity([]) is Severity.none
    assert max_severity([Severity.low, Severity.high, Severity.medium]) is Severity.high
    assert worst_severity([make_finding("a", severity=Severity.critical)]) is Severity.critical
