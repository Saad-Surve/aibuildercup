"""Brand Voice reviewer (`brand_voice`)."""

from app.agents.reviewer_base import LlmReviewer
from app.schemas.analysis import AnalysisDimension

FOCUS = """\
You review consistency with the creator's stated voice.

Use the persona in the task as the reference. Flag places where the speaker's tone,
vocabulary, or stated values diverge from that voice: too formal, too casual, promising
things the persona would not promise, contradicting the creator's stated priorities, or
sounding like a different creator entirely.

If no persona is provided, judge internal consistency instead: does the voice stay
stable through the piece?

findingType vocabulary: tone_drift, voice_inconsistency, value_conflict,
off_brand_claim, strength."""


class BrandVoiceReviewer(LlmReviewer):
    dimension = AnalysisDimension.brand_voice
    focus = FOCUS
