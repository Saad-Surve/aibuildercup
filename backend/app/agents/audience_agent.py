"""Audience Fit reviewer (`audience_fit`)."""

from app.agents.reviewer_base import LlmReviewer
from app.schemas.analysis import AnalysisDimension

FOCUS = """\
You review how well the content matches the intended audience.

Use the creator persona and intended audience in the task. Check: assumed knowledge
(both too much and too little); vocabulary and register; whether the examples come
from the audience's world; whether what the content promises matches what that
audience came for; whether the tone talks up, down, or across to them.

findingType vocabulary: knowledge_gap, register_mismatch, alienating_example,
promise_mismatch, condescending, strength."""


class AudienceFitReviewer(LlmReviewer):
    dimension = AnalysisDimension.audience_fit
    focus = FOCUS
