"""Analysis run, reviewer, finding, and heatmap schemas.

Public shapes match `contracts/openapi.yaml`; the persisted shapes match
`docs/technical-design/db-design.md` section 5.
"""

from datetime import datetime
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.interest_calibration import InterestBaselineSource


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


class FindingDecisionInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    status: Literal["accepted", "revised", "dismissed"]
    note: str | None = Field(
        default=None, max_length=2000, exclude_if=lambda value: value is None
    )
    revisedAction: str | None = Field(
        default=None, min_length=1, max_length=4000, exclude_if=lambda value: value is None
    )

    @model_validator(mode="after")
    def validate_revision(self) -> "FindingDecisionInput":
        if self.status == "revised" and not self.revisedAction:
            raise ValueError("A revised decision needs a proposed action.")
        if self.status != "revised" and self.revisedAction is not None:
            raise ValueError("Only revised decisions can include revisedAction.")
        return self


class FindingDecision(FindingDecisionInput):
    decidedAt: datetime
    decidedBy: str


class FindingDecisionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    decision: FindingDecisionInput | None


class AdjudicationEvidence(BaseModel):
    timestampMs: int = Field(ge=0)
    framePath: str
    clipPath: str | None = None


class FindingAdjudication(BaseModel):
    verdict: Literal["confirm", "downgrade", "reject"]
    reason: str = Field(min_length=1, max_length=2000)
    adjustedSeverity: Severity | None = None
    evidence: AdjudicationEvidence
    checkedAt: datetime
    model: str
    promptVersion: str


class FindingReconciliation(BaseModel):
    clusterId: str
    findingIds: list[str]
    recommendation: str
    reason: str
    model: str
    promptVersion: str
    reconciledAt: datetime


class AdjudicatorSummary(BaseModel):
    model: str
    promptVersion: str
    callCount: int = 0
    findingCallCount: int = 0
    conflictCallCount: int = 0
    errorCount: int = 0
    skippedCount: int = 0
    costEstimateUsd: float = 0.0
    tokenUsage: TokenUsage = Field(default_factory=TokenUsage)
    errors: list[str] = Field(default_factory=list)


class FindingLibraryLink(BaseModel):
    """An example from earlier creator work, never evidence about this video."""

    nodeId: str
    sourceTitle: str
    sourceUrl: str | None = None
    excerpt: str
    startMs: int | None = Field(default=None, ge=0)
    similarity: float = Field(ge=-1, le=1, allow_inf_nan=False)
    note: str


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
    decision: FindingDecision | None = None
    adjudication: FindingAdjudication | None = None
    reconciliation: FindingReconciliation | None = None
    libraryLinks: list[FindingLibraryLink] = Field(default_factory=list, max_length=1)


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
    assetId: str | None = None
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
    adjudicator: AdjudicatorSummary | None = None
    error: dict[str, Any] | None = None
    createdAt: datetime
    updatedAt: datetime


class ReviewerGroundingSource(BaseModel):
    """One web source the reviewer verified a claim against."""

    title: str = ""
    url: str = ""


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
    #: Web grounding: the search queries run and the sources used (empty when not grounded).
    groundingQueries: list[str] = Field(default_factory=list)
    groundingSources: list[ReviewerGroundingSource] = Field(default_factory=list)
    #: Google-provided Search Suggestions HTML; must be rendered when present.
    groundingSearchSuggestions: str = ""
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


class HeatmapCoverage(BaseModel):
    """A span a reviewer actually read. Time inside it with no bin had nothing to flag."""

    dimension: AnalysisDimension
    startMs: int
    endMs: int


class HeatmapResponse(BaseModel):
    bins: list[HeatmapBin]
    #: Reviewed spans per dimension. Empty for runs created before coverage was recorded.
    coverage: list[HeatmapCoverage] = Field(default_factory=list)


class InterestPoint(BaseModel):
    """One five-second bin of the predicted-interest curve."""

    startMs: int
    endMs: int
    #: Relative interest within this video, 0 (lowest) to 1 (highest). Not retention.
    value: float = Field(ge=0, le=1)
    #: The typical drop-off at this point in a video, on the same scale as `value`. Where
    #: `value` sits above it the content is predicted to beat its place in the video.
    baseline: float = Field(default=0, ge=0, le=1)
    #: What pushes this bin up or down, as short phrases ("a payoff", "a long pause").
    driversUp: list[str] = Field(default_factory=list)
    driversDown: list[str] = Field(default_factory=list)
    #: Measured and rated signals: wpm, speechRatio, pauseMs, novelty, and, when the
    #: Gemini pass ran, hook/payoff/novelty/open_loop/emotion/humor/practical/visual/tangent
    #: on a 1-5 scale.
    signals: dict[str, float] = Field(default_factory=dict)


class InterestMoment(BaseModel):
    """A stretch that most beats (peak) or falls short of (dip) the typical drop-off."""

    kind: Literal["peak", "dip"]
    startMs: int
    endMs: int
    value: float
    drivers: list[str] = Field(default_factory=list)
    #: Findings from the same run that overlap this moment.
    findingIds: list[str] = Field(default_factory=list)


class InterestCalibration(BaseModel):
    """How the bundled model scored on held-out public videos."""

    label: str
    videos: int
    channels: int
    testVideos: int
    heldOutSpearman: float
    positionBaselineSpearman: float
    #: Correlation of predicted and true deviation from the typical drop-off: how much
    #: the content features explain beyond position alone.
    liftSpearman: float = 0.0
    peakPrecision: float
    dipPrecision: float
    trainedAt: str


class InterestCurve(BaseModel):
    analysisRunId: str
    status: Literal["ready", "failed"]
    modelVersion: str = ""
    #: `transcript+gemini` when the Gemini signal pass ran, else the transcript-only model.
    featureSource: Literal["transcript+gemini", "transcript"] = "transcript"
    binMs: int = 5000
    durationMs: int = 0
    points: list[InterestPoint] = Field(default_factory=list)
    peaks: list[InterestMoment] = Field(default_factory=list)
    dips: list[InterestMoment] = Field(default_factory=list)
    calibration: InterestCalibration | None = None
    baselineSource: InterestBaselineSource = Field(default_factory=InterestBaselineSource)
    costEstimateUsd: float = 0.0
    error: dict[str, Any] | None = None
    createdAt: datetime | None = None
