"""Audience and Brand reviewer (`audience_brand`).

Consolidated from the retired `audience_fit` and `brand_voice` reviewers: with a sparse
persona, `brand_voice` fell back to general tone consistency and repeated the register
critiques `audience_fit` had already made.
"""

from app.agents.reviewer_base import LlmReviewer
from app.schemas.analysis import AnalysisDimension

FOCUS = """\
You review how well the content matches the intended audience and the creator's stated
brand voice. Use the creator persona and intended audience in the task.

AUDIENCE FIT:
Assumed knowledge (both too much and too little); vocabulary and register; whether the
examples come from the audience's world; whether what the content promises matches what
that audience came for; whether the tone talks up, down, or across to them.

BRAND VOICE:
Where the speaker's tone, vocabulary, or stated values diverge from the persona: too
formal, too casual, promising things the persona would not promise, contradicting the
creator's stated priorities, or sounding like a different creator entirely. If no persona
is provided, judge internal consistency instead: does the voice stay stable through the
piece?

findingType vocabulary (severity in brackets):
  strength              [none]   an exceptional audience/brand match (score 5)
  knowledge_gap         [medium]
  register_mismatch     [medium]
  alienating_example    [medium, high]
  promise_mismatch      [high]
  condescending         [medium, high]
  tone_drift            [medium]
  voice_inconsistency   [medium]
  value_conflict        [high]
  off_brand_claim       [medium, high]"""


class AudienceBrandReviewer(LlmReviewer):
    dimension = AnalysisDimension.audience_brand
    focus = FOCUS
    finding_types = (
        "strength",
        "knowledge_gap",
        "register_mismatch",
        "alienating_example",
        "promise_mismatch",
        "condescending",
        "tone_drift",
        "voice_inconsistency",
        "value_conflict",
        "off_brand_claim",
    )
