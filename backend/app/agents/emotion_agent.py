"""Emotional Impact reviewer (`emotional_impact`)."""

from app.agents.reviewer_base import LlmReviewer
from app.schemas.analysis import AnalysisDimension

FOCUS = """\
You review the emotional arc of the content.

Check: is there any emotional stake at all, or is it flat? Does the piece build, or
just list? Are people and consequences made concrete rather than kept abstract? Is
there a moment that lands - a turn, an admission, a surprise? Is the emotional
register right for the subject (for example comedy over something that deserves care)?

findingType vocabulary (severity in brackets):
  emotional_peak       [none]   a moment that genuinely lands (score 5)
  flat                 [medium]
  missed_moment        [medium]
  inappropriate_tone   [high]
  emotional_misstep    [medium]
  empathy_gap          [medium]"""


class EmotionalImpactReviewer(LlmReviewer):
    dimension = AnalysisDimension.emotional_impact
    focus = FOCUS
    finding_types = (
        "emotional_peak",
        "flat",
        "missed_moment",
        "inappropriate_tone",
        "emotional_misstep",
        "empathy_gap",
    )
