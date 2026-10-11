"""Emotional Impact reviewer (`emotional_impact`)."""

from app.agents.reviewer_base import LlmReviewer
from app.schemas.analysis import AnalysisDimension

FOCUS = """\
You review the emotional arc of the content.
Match the creator's genre and purpose. A calm technical tutorial can be effective
without a dramatic story. Do not confuse a neutral transcript with flat vocal delivery;
the supplied frames and silent clip tools cannot establish vocal tone.

Check: is there any emotional stake at all, or is it flat? Does the piece build, or
just list? Are people and consequences made concrete rather than kept abstract? Is
there a moment that lands - a turn, an admission, a surprise? Is the emotional
register right for the subject (for example comedy over something that deserves care)?

When an important consequence stays abstract, suggest one concrete way to make that
existing stake clear. Never fabricate a personal anecdote, testimonial, or feeling for
the creator. Give usable wording based on the material that is actually present.

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
