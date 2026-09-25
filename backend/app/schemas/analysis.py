"""Analysis run, reviewer, finding, and heatmap schemas.

Public shapes match `contracts/openapi.yaml`; the persisted shapes match
`docs/technical-design/db-design.md` section 5.
"""

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class AnalysisDimension(StrEnum):
    """Reviewer dimensions. Core dimensions always run; the rest are opt-in."""

    truth_evidence = "truth_evidence"
    clarity = "clarity"
    structure_pacing = "structure_pacing"
    legal_safety = "legal_safety"
    cultural_localization = "cultural_localization"
    platform_fit = "platform_fit"
    audience_fit = "audience_fit"
    brand_voice = "brand_voice"
    engagement_retention = "engagement_retention"
    emotional_impact = "emotional_impact"
    seo_discoverability = "seo_discoverability"
    visual_accessibility = "visual_accessibility"
    conversion_cta = "conversion_cta"


#: Always-on dimensions (`docs/technical-design/backend-plan.md` section 8).
CORE_DIMENSIONS: tuple[AnalysisDimension, ...] = (
    AnalysisDimension.truth_evidence,
    AnalysisDimension.clarity,
    AnalysisDimension.structure_pacing,
    AnalysisDimension.legal_safety,
    AnalysisDimension.cultural_localization,
    AnalysisDimension.platform_fit,
)

#: Dimensions that need sampled frames / clip review. Tier-2 only: a text-only run
#: still reviews them from the transcript, so they stay selectable.
VISUAL_DIMENSIONS: frozenset[AnalysisDimension] = frozenset(
    {AnalysisDimension.visual_accessibility}
)


def resolve_dimensions(requested: list[AnalysisDimension]) -> list[AnalysisDimension]:
    """Core dimensions plus whatever was requested, in canonical order."""
    wanted = set(CORE_DIMENSIONS) | set(requested)
    return [dimension for dimension in AnalysisDimension if dimension in wanted]


class Severity(StrEnum):
    none = "none"
    low = "low"
    medium = "medium"
    high = "high"
    critical = "critical"


#: Ordinal used to pick the worst severity in a bin.
SEVERITY_RANK: dict[Severity, int] = {
    Severity.none: 0,
    Severity.low: 1,
    Severity.medium: 2,
    Severity.high: 3,
    Severity.critical: 4,
}


def max_severity(severities: list[Severity]) -> Severity:
    if not severities:
        return Severity.none
    return max(severities, key=lambda severity: SEVERITY_RANK[severity])


class HeatmapColor(StrEnum):
    green = "green"
    yellow = "yellow"
    orange = "orange"
    red = "red"


class AnalysisRunStatus(StrEnum):
    queued = "queued"
    running = "running"
    ready = "ready"
    partial_failure = "partial_failure"
    failed = "failed"


class ReviewerRunStatus(StrEnum):
    queued = "queued"
    running = "running"
    succeeded = "succeeded"
    failed = "failed"


class TokenUsage(BaseModel):
    input: int = 0
    output: int = 0


class FindingEvidence(BaseModel):
    quote: str = ""
    explanation: str = ""


class Finding(BaseModel):
    """One reviewer observation over a span of the transcript.

    Reviewers emit spans that cover the reviewed window, including `severity: none`
    for parts that are fine. That is what keeps the heatmap track continuous.
    """

    findingId: str
    dimension: AnalysisDimension
    reviewerRunId: str | None = None
    segmentId: str | None = None
    startMs: int = Field(ge=0)
    endMs: int = Field(ge=0)
    score: float = Field(ge=0, le=10)
    confidence: float = Field(ge=0, le=1)
    severity: Severity
    findingType: str = ""
    evidence: FindingEvidence = Field(default_factory=FindingEvidence)
    suggestion: str = ""
    citations: list[dict[str, Any]] = Field(default_factory=list)


class HeatmapBin(BaseModel):
    binId: str
    dimension: AnalysisDimension
    startMs: int
    endMs: int
    score: float
    severity: Severity
    color: HeatmapColor
    findingIds: list[str] = Field(default_factory=list)


class AnalysisRequest(BaseModel):
    dimensions: list[AnalysisDimension] = Field(default_factory=list)
    platform: str = "youtube"
    includeVisualReview: bool = False
    transcriptVersion: int | None = None


class AnalysisRun(BaseModel):
    analysisRunId: str
    jobId: str
    status: AnalysisRunStatus
    transcriptId: str
    sourceAssetId: str | None = None
    personaVersion: int | None = None
    fanoutStrategy: str = "two_tier"
    chunkCount: int = 0
    requestedDimensions: list[AnalysisDimension] = Field(default_factory=list)
    completedDimensions: list[AnalysisDimension] = Field(default_factory=list)
    overallScore: float | None = None
    scoreByDimension: dict[str, float] = Field(default_factory=dict)
    findingCounts: dict[str, int] = Field(default_factory=dict)
    modelConfigVersion: str
    promptVersion: str
    costEstimateUsd: float = 0.0
    error: dict[str, Any] | None = None
    createdAt: datetime
    updatedAt: datetime


class ReviewerRun(BaseModel):
    reviewerRunId: str
    dimension: AnalysisDimension
    status: ReviewerRunStatus
    findingCount: int = 0
    costEstimateUsd: float = 0.0
    durationMs: int = 0
    model: str | None = None
    inputSegmentCount: int = 0
    tokenUsage: TokenUsage = Field(default_factory=TokenUsage)
    error: dict[str, Any] | None = None
    startedAt: datetime | None = None
    finishedAt: datetime | None = None


class AnalysisStartResponse(BaseModel):
    analysisRunId: str
    jobId: str
    status: str


class AnalysisRunList(BaseModel):
    items: list[AnalysisRun]


class ReviewerRunList(BaseModel):
    items: list[ReviewerRun]


class FindingList(BaseModel):
    items: list[Finding]


class HeatmapResponse(BaseModel):
    bins: list[HeatmapBin]
