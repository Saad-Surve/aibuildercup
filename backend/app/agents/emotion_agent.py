"""Emotional Impact reviewer (`emotional_impact`)."""

from app.agents.reviewer_base import LlmReviewer
from app.schemas.analysis import AnalysisDimension

FOCUS = """\
You review the emotional arc of the content.

Check: is there any emotional stake at all, or is it flat? Does the piece build, or
just list? Are people and consequences made concrete rather than kept abstract? Is
there a moment that lands - a turn, an admission, a surprise? Is the emotional
register right for the subject (for example comedy over something that deserves care)?

findingType vocabulary: flat, emotional_peak, missed_moment, inappropriate_tone,
emotional_misstep, empathy_gap, strength."""


class EmotionalImpactReviewer(LlmReviewer):
    dimension = AnalysisDimension.emotional_impact
    focus = FOCUS
