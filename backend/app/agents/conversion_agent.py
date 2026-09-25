"""Conversion and Call to Action reviewer (`conversion_cta`)."""

from app.agents.reviewer_base import LlmReviewer
from app.schemas.analysis import AnalysisDimension

FOCUS = """\
You review the calls to action.

Check: is there a call to action at all? Is it clear what the viewer should do next?
Is it placed where the viewer has a reason to act? Are there competing asks? Is the ask
proportionate to the value just delivered? Does it read as a request rather than a
demand? Does it match the platform's norms for asking?

findingType vocabulary: missing_cta, unclear_cta, competing_asks, mistimed_cta,
heavy_handed, good_cta."""


class ConversionCtaReviewer(LlmReviewer):
    dimension = AnalysisDimension.conversion_cta
    focus = FOCUS
