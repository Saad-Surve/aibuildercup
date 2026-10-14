"""Read-only review comparison payloads; see contracts/openapi.yaml."""

from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.analysis import AnalysisDimension, Finding, HeatmapBin, HeatmapCoverage


class ComparisonSpan(BaseModel):
    startMs: int
    endMs: int


class ComparisonTimeSegment(BaseModel):
    sourceStartMs: int
    sourceEndMs: int
    targetStartMs: int
    targetEndMs: int


class ComparisonAlignment(BaseModel):
    method: Literal["identity", "rough_cut", "transcript", "unaligned"]
    confidence: float
    targetTimeline: Literal["source", "target"]
    segments: list[ComparisonTimeSegment] = Field(default_factory=list)
    removedSpans: list[ComparisonSpan] = Field(default_factory=list)
    note: str


class ComparisonBin(HeatmapBin):
    nativeStartMs: int
    nativeEndMs: int


class ComparisonInterestPoint(ComparisonSpan):
    value: float
    baseline: float


class ComparisonRun(BaseModel):
    runId: str
    sourceAssetId: str | None
    durationMs: int
    status: Literal["ready", "partial_failure"]
    dimensions: list[AnalysisDimension]
    bins: list[ComparisonBin]
    unmappedBins: list[ComparisonBin] = Field(default_factory=list)
    coverage: list[HeatmapCoverage] = Field(default_factory=list)
    interest: list[ComparisonInterestPoint] = Field(default_factory=list)


class ComparisonFinding(BaseModel):
    status: Literal["resolved", "persists", "new", "uncompared"]
    reason: Literal[
        "removed",
        "no_match",
        "matched",
        "unmatched_target",
        "alignment_uncertain",
        "review_incomplete",
    ]
    baseFinding: Finding | None = None
    targetFinding: Finding | None = None
    sourceSpans: list[ComparisonSpan] = Field(default_factory=list)
    accepted: bool = False


class ComparisonBinCounts(BaseModel):
    total: int = 0
    critical: int = 0
    high: int = 0
    medium: int = 0


class ComparisonInterestChange(BaseModel):
    meanAboveBaselineBefore: float
    meanAboveBaselineAfter: float
    delta: float
    note: str


class ComparisonSummary(BaseModel):
    flaggedBinsBefore: ComparisonBinCounts
    flaggedBinsAfter: ComparisonBinCounts
    durationMsBefore: int
    durationMsAfter: int
    acceptedFindingsTotal: int
    acceptedFindingsResolved: int
    newFindingsCount: int
    newIssuesCount: int
    uncomparedFindingsCount: int
    interestChange: ComparisonInterestChange | None = None


class AnalysisComparison(BaseModel):
    base: ComparisonRun
    target: ComparisonRun
    summary: ComparisonSummary
    alignment: ComparisonAlignment
    findings: list[ComparisonFinding]
