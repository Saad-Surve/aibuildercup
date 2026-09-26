"""Conversion and Session Continuity reviewer (`conversion_cta`)."""

from app.agents.reviewer_base import LlmReviewer
from app.schemas.analysis import AnalysisDimension

FOCUS = """\
You review calls to action (CTAs), community prompts, and session-extension hooks.

WHAT TO EVALUATE:
1. Outro Drop-Off Risk: does the creator signal the video is ending ("Well guys, that's
   all for today...") before delivering the final value or CTA, triggering instant viewer
   departure?
2. Value-to-Ask Ratio: is the request proportional to the value just delivered? (For
   example, asking for a course purchase after a 30-second tip is poorly matched.)
3. Session Extension (YouTube): does the end CTA direct viewers to a specific next video
   rather than a generic channel subscribe?
4. Comment Conversation Triggers: are viewers asked open-ended or polarizing questions
   that make commenting effortless?

findingType vocabulary (severity in brackets):
  high_converting_cta      [none]          a well-placed, proportionate CTA (score 5)
  premature_outro_dropoff  [high]
  friction_heavy_ask       [medium, high]
  competing_cta_overload   [medium]
  generic_passive_ask      [low, medium]"""


class ConversionCtaReviewer(LlmReviewer):
    dimension = AnalysisDimension.conversion_cta
    focus = FOCUS
    finding_types = (
        "high_converting_cta",
        "premature_outro_dropoff",
        "friction_heavy_ask",
        "competing_cta_overload",
        "generic_passive_ask",
    )
