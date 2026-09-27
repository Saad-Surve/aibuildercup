"""Analysis run, reviewer, finding, and heatmap schemas.

Public shapes match `contracts/openapi.yaml`; the persisted shapes match
`docs/technical-design/db-design.md` section 5.
"""

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class AnalysisDimension(StrEnum):
    """Reviewer dimensions.

    Active dimensions are the 2026-09 panel: the old `structure_pacing` and
    `engagement_retention` merged into `pacing_retention`, `audience_fit` and
    `brand_voice` merged into `audience_brand`, and `seo_discoverability` /
    `visual_accessibility` were dropped (invalid or harmful without packaging /
    visual input). The retired values are kept so historical runs still deserialize;
    they are never requested or run again (see `LEGACY_DIMENSIONS`).
    """

    truth_evidence = "truth_evidence"
    clarity = "clarity"
    pacing_retention = "pacing_retention"
    legal_safety = "legal_safety"
    cultural_localization = "cultural_localization"
    platform_fit = "platform_fit"
    audience_brand = "audience_brand"
    emotional_impact = "emotional_impact"
    conversion_cta = "conversion_cta"

    # --- retired (read-only; kept for historical runs) ---
    structure_pacing = "structure_pacing"
    engagement_retention = "engagement_retention"
    audience_fit = "audience_fit"
    brand_voice = "brand_voice"
    seo_discoverability = "seo_discoverability"
    visual_accessibility = "visual_accessibility"


#: Retired dimensions: never selected for a new run, still readable on old ones.
LEGACY_DIMENSIONS: frozenset[AnalysisDimension] = frozenset(
    {
        AnalysisDimension.structure_pacing,
        AnalysisDimension.engagement_retention,
        AnalysisDimension.audience_fit,
        AnalysisDimension.brand_voice,
        AnalysisDimension.seo_discoverability,
        AnalysisDimension.visual_accessibility,
    }
)

#: Selectable dimensions, in canonical order.
ACTIVE_DIMENSIONS: tuple[AnalysisDimension, ...] = tuple(
    dimension for dimension in AnalysisDimension if dimension not in LEGACY_DIMENSIONS
)

#: Always-on dimensions (`docs/technical-design/backend-plan.md` section 8).
CORE_DIMENSIONS: tuple[AnalysisDimension, ...] = (
    AnalysisDimension.truth_evidence,
    AnalysisDimension.clarity,
    AnalysisDimension.pacing_retention,
    AnalysisDimension.legal_safety,
    AnalysisDimension.cultural_localization,
    AnalysisDimension.platform_fit,
)


def resolve_dimensions(requested: list[AnalysisDimension]) -> list[AnalysisDimension]:
    """Core dimensions plus whatever was requested, in canonical order.

    Legacy dimensions are ignored, so a stale client cannot resurrect a retired
    reviewer.
    """
    wanted = set(CORE_DIMENSIONS) | {
        dimension for dimension in requested if dimension not in LEGACY_DIMENSIONS
    }
    return [dimension for dimension in ACTIVE_DIMENSIONS if dimension in wanted]


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
    #: Free-form reasoning emitted before the score, so the model reasons then grades.
    critique_and_reasoning: str = ""


class Finding(BaseModel):
    """One reviewer observation over a span of the transcript.

    Reviewers report exception-first: an actionable flaw, or an exceptional strength
    worth reinforcing. Untouched time simply has no finding; the heatmap shows gaps
    rather than invented scores.
    """

    findingId: str
    dimension: AnalysisDimension
    reviewerRunId: str | None = None
    segmentId: str | None = None
    startMs: int = Field(ge=0)
    endMs: int = Field(ge=0)
    #: Discrete quality, higher is better: 1 broken ... 5 exceptional.
    score: int = Field(ge=1, le=5)
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


class ReviewerToolCall(BaseModel):
    """One footage tool a reviewer called (for the UI's evidence trail)."""

    tool: str
    timestampMs: int = 0
    label: str = ""
    mimeType: str = ""
    #: Cloud Storage object holding the frame/clip; empty when the call failed.
    contentPath: str = ""
    ok: bool = True


class ReviewerRun(BaseModel):
    reviewerRunId: str
    dimension: AnalysisDimension
    status: ReviewerRunStatus
    findingCount: int = 0
    costEstimateUsd: float = 0.0
    durationMs: int = 0
    model: str | None = None
    inputSegmentCount: int = 0
    #: Frames/clips the reviewer pulled in through the footage tools.
    toolCalls: list[ReviewerToolCall] = Field(default_factory=list)
    tokenUsage: TokenUsage = Field(default_factory=TokenUsage)
    error: dict[str, Any] | None = None
    startedAt: datetime | None = None
    finishedAt: datetime | None = None


class AnalysisStartResponse(BaseModel):
    analysisRunId: str
    jobId: str
    status: str


class ContextArtifactUrl(BaseModel):
    """A short-lived signed URL for one reviewer-fetched frame/clip."""

    url: str
    contentType: str = ""
    expiresIn: int = 900


class AnalysisRunList(BaseModel):
    items: list[AnalysisRun]


class ReviewerRunList(BaseModel):
    items: list[ReviewerRun]


class FindingList(BaseModel):
    items: list[Finding]


class HeatmapResponse(BaseModel):
    bins: list[HeatmapBin]
