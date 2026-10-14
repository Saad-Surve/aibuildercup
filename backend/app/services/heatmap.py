"""Heatmap aggregation: findings in, UI-ready bins and summaries out.

Pure functions only — no I/O, no model calls. The rules come from
`docs/technical-design/backend-plan.md` section 9:

1. Clamp timestamps to the transcript duration.
2. Map findings to fixed-size bins (five seconds by default).
3. Aggregate overlapping scores per dimension.
4. Preserve every finding id in its bin.
5. Convert score/severity to a UI color.

Scores are quality scores on a 1-5 scale (higher is better), so a bin's color follows
the score bands and a `critical` finding forces red regardless of the band.

Bins only exist where a finding exists. Reviewers report exception-first (a flaw, or an
exceptional strength), so a finished run yields an event-based track with gaps where
nothing needed saying, rather than invented scores for untouched time.
"""

from dataclasses import dataclass, field

from app.schemas.analysis import (
    AnalysisDimension,
    Finding,
    HeatmapBin,
    HeatmapColor,
    HeatmapCoverage,
    Severity,
    max_severity,
)

#: Fixed bin width. Matches "initially five seconds" in the design.
BIN_MS = 5000

_SEVERITY_KEYS: tuple[Severity, ...] = (
    Severity.none,
    Severity.low,
    Severity.medium,
    Severity.high,
    Severity.critical,
)


def color_for(score: float, severity: Severity) -> HeatmapColor:
    """Map a bin to its UI color.

    A critical finding is red whatever the average score says — the worst moment
    must never look fine because it was averaged with a strong neighbour.
    """
    if severity is Severity.critical:
        return HeatmapColor.red
    if score >= 4:
        return HeatmapColor.green
    if score >= 3:
        return HeatmapColor.yellow
    if score >= 2:
        return HeatmapColor.orange
    return HeatmapColor.red


def bin_id_for(dimension: AnalysisDimension | str, start_ms: int) -> str:
    """Deterministic document id, so re-aggregation is idempotent."""
    return f"{dimension}-{start_ms}"


def normalize_span(
    start_ms: int, end_ms: int, *, duration_ms: int
) -> tuple[int, int] | None:
    """Clamp a finding span to `[0, duration_ms]`. None when nothing is left."""
    start = min(max(0, int(start_ms)), duration_ms)
    end = min(max(0, int(end_ms)), duration_ms)
    if end <= start:
        # A zero-length finding is a point observation: give it one millisecond so
        # it can still land in a bin.
        end = min(start + 1, duration_ms)
    if end <= start:
        return None
    return start, end


@dataclass
class BinAccumulator:
    """Running aggregate for one (dimension, bin) pair."""

    dimension: AnalysisDimension
    index: int
    bin_ms: int
    total_weight: int = 0
    weighted_score: float = 0.0
    severities: list[Severity] = field(default_factory=list)
    finding_ids: list[str] = field(default_factory=list)

    @property
    def start_ms(self) -> int:
        return self.index * self.bin_ms

    @property
    def end_ms(self) -> int:
        return self.start_ms + self.bin_ms

    def add(self, finding: Finding, overlap_ms: int) -> None:
        self.total_weight += overlap_ms
        self.weighted_score += finding.score * overlap_ms
        self.severities.append(finding.severity)
        if finding.findingId not in self.finding_ids:
            self.finding_ids.append(finding.findingId)

    def to_bin(self) -> HeatmapBin:
        score = round(self.weighted_score / self.total_weight, 2) if self.total_weight else 0.0
        severity = max_severity(self.severities)
        return HeatmapBin(
            binId=bin_id_for(self.dimension, self.start_ms),
            dimension=self.dimension,
            startMs=self.start_ms,
            endMs=self.end_ms,
            score=score,
            severity=severity,
            color=color_for(score, severity),
            findingIds=list(self.finding_ids),
        )


def effective_findings(findings: list[Finding]) -> list[Finding]:
    """Adjudication affects aggregation, never the stored reviewer score or creator intent."""
    effective: list[Finding] = []
    for finding in findings:
        check = finding.adjudication
        if check is not None and check.verdict == "reject":
            continue
        if (
            check is not None
            and check.verdict == "downgrade"
            and check.adjustedSeverity is not None
        ):
            finding = finding.model_copy(update={"severity": check.adjustedSeverity})
        effective.append(finding)
    return effective


def aggregate_bins(
    findings: list[Finding],
    *,
    duration_ms: int,
    bin_ms: int = BIN_MS,
) -> list[HeatmapBin]:
    """Aggregate findings into fixed-size per-dimension bins.

    Returns one bin per (dimension, time window) that at least one finding
    touches, ordered by dimension then time. Bins are dropped rather than padded
    with invented scores when no finding covers them.
    """
    if bin_ms <= 0:
        raise ValueError("bin_ms must be positive")
    if duration_ms <= 0 or not findings:
        return []

    accumulators: dict[tuple[AnalysisDimension, int], BinAccumulator] = {}
    for finding in effective_findings(findings):
        span = normalize_span(finding.startMs, finding.endMs, duration_ms=duration_ms)
        if span is None:
            continue
        start, end = span
        first_index = start // bin_ms
        last_index = (end - 1) // bin_ms
        for index in range(first_index, last_index + 1):
            bin_start = index * bin_ms
            overlap = min(end, bin_start + bin_ms) - max(start, bin_start)
            if overlap <= 0:
                continue
            key = (finding.dimension, index)
            accumulator = accumulators.get(key)
            if accumulator is None:
                accumulator = BinAccumulator(
                    dimension=finding.dimension, index=index, bin_ms=bin_ms
                )
                accumulators[key] = accumulator
            accumulator.add(finding, overlap)

    dimension_order = {dimension: i for i, dimension in enumerate(AnalysisDimension)}
    ordered = sorted(
        accumulators.values(),
        key=lambda acc: (dimension_order[acc.dimension], acc.index),
    )
    return [accumulator.to_bin() for accumulator in ordered]


def merge_coverage(
    spans_by_dimension: dict[AnalysisDimension, list[tuple[int, int]]],
    *,
    duration_ms: int,
) -> list[HeatmapCoverage]:
    """Clamp and merge each dimension's reviewed windows into ordered, disjoint spans.

    A window counts only when its reviewer actually returned for it, so a failed chunk
    shows as unreviewed rather than as "nothing to flag".
    """
    dimension_order = {dimension: i for i, dimension in enumerate(AnalysisDimension)}
    merged: list[HeatmapCoverage] = []
    for dimension in sorted(spans_by_dimension, key=lambda d: dimension_order[d]):
        clamped = sorted(
            (max(0, start), min(duration_ms, end))
            for start, end in spans_by_dimension[dimension]
            if min(duration_ms, end) > max(0, start)
        )
        current: list[int] | None = None
        for start, end in clamped:
            if current is not None and start <= current[1]:
                current[1] = max(current[1], end)
                continue
            if current is not None:
                merged.append(
                    HeatmapCoverage(dimension=dimension, startMs=current[0], endMs=current[1])
                )
            current = [start, end]
        if current is not None:
            merged.append(
                HeatmapCoverage(dimension=dimension, startMs=current[0], endMs=current[1])
            )
    return merged


@dataclass
class FindingSummary:
    """Roll-up statistics for an analysis run."""

    counts: dict[str, int] = field(default_factory=dict)
    score_by_dimension: dict[str, float] = field(default_factory=dict)
    overall_score: float | None = None


def summarize_findings(findings: list[Finding]) -> FindingSummary:
    """Per-severity counts, per-dimension scores, and the overall score.

    Dimension scores are duration-weighted means so a long observation is not
    drowned out by a one-second blip; the overall score is the unweighted mean of
    the dimension scores so one noisy dimension cannot dominate the run.
    """
    findings = effective_findings(findings)
    counts = {severity.value: 0 for severity in _SEVERITY_KEYS}
    for finding in findings:
        counts[finding.severity.value] += 1

    weighted: dict[AnalysisDimension, list[tuple[float, int]]] = {}
    for finding in findings:
        weight = max(1, finding.endMs - finding.startMs)
        weighted.setdefault(finding.dimension, []).append((finding.score, weight))

    score_by_dimension: dict[str, float] = {}
    for dimension, entries in weighted.items():
        total_weight = sum(weight for _, weight in entries) or 1
        mean = sum(score * weight for score, weight in entries) / total_weight
        score_by_dimension[dimension.value] = round(mean, 2)

    overall = (
        round(sum(score_by_dimension.values()) / len(score_by_dimension), 2)
        if score_by_dimension
        else None
    )
    return FindingSummary(
        counts=counts, score_by_dimension=score_by_dimension, overall_score=overall
    )


def worst_severity(findings: list[Finding]) -> Severity:
    """The worst severity present, or `none` for an empty list."""
    return max_severity([finding.severity for finding in effective_findings(findings)])


__all__ = [
    "BIN_MS",
    "BinAccumulator",
    "FindingSummary",
    "aggregate_bins",
    "bin_id_for",
    "color_for",
    "merge_coverage",
    "normalize_span",
    "summarize_findings",
    "worst_severity",
]
