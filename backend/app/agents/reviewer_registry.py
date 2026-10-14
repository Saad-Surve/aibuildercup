"""The shared specialist registry used by fan-out and the all-rubric review."""

from app.agents.audience_brand_agent import AudienceBrandReviewer
from app.agents.clarity_agent import ClarityReviewer
from app.agents.conversion_agent import ConversionCtaReviewer
from app.agents.cultural_agent import CulturalLocalizationReviewer
from app.agents.emotion_agent import EmotionalImpactReviewer
from app.agents.pacing_agent import PacingRetentionReviewer
from app.agents.platform_agent import PlatformFitReviewer
from app.agents.reviewer_base import LlmReviewer
from app.agents.safety_agent import LegalSafetyReviewer
from app.agents.truth_agent import TruthEvidenceReviewer
from app.schemas.analysis import AnalysisDimension

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
