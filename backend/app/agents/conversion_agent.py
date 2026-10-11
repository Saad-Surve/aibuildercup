"""Conversion and Session Continuity reviewer (`conversion_cta`)."""

from app.agents.reviewer_base import LlmReviewer
from app.schemas.analysis import AnalysisDimension

FOCUS = """\
You review calls to action (CTAs), community prompts, and session-extension hooks.
Use the creator's brief and format to decide whether an ask is appropriate. A useful
explanation or personal story does not need a sales pitch, comment bait, or several CTAs.

WHAT TO EVALUATE:
1. Outro Drop-Off Risk: does the creator signal the video is ending ("Well guys, that's
   all for today...") before delivering the promised final value or relevant CTA?
2. Value-to-Ask Ratio: is the request proportional to the value just delivered? (For
   example, asking for a course purchase after a 30-second tip is poorly matched.)
3. Session Extension (YouTube): does the end CTA direct viewers to a specific next video
   rather than a generic channel subscribe?
4. Comment Conversation Triggers: are viewers asked an easy-to-answer question related
   to the actual subject? Do not introduce polarizing bait to chase comments.

Give replacement CTA wording that names one useful next step, with no invented offer,
link, product, or video title. If the intended next step is missing, only flag it when
the brief establishes that goal; anchor the suggested addition near the ending.
A sign-off after the value and relevant CTA have already been delivered is normal,
not premature outro drop-off. Do not invent a related video the creator can link to.
Only suggest a session-extension link when the brief or context establishes one exists.

findingType vocabulary (severity in brackets):
  high_converting_cta      [none]          a well-placed, proportionate CTA (score 5)
  premature_outro_dropoff  [high]
  friction_heavy_ask       [medium, high]
  competing_cta_overload   [medium]
  generic_passive_ask      [low, medium]
  missing_next_step       [low, medium]"""


class ConversionCtaReviewer(LlmReviewer):
    dimension = AnalysisDimension.conversion_cta
    focus = FOCUS
    finding_types = (
        "high_converting_cta",
        "premature_outro_dropoff",
        "friction_heavy_ask",
        "competing_cta_overload",
        "generic_passive_ask",
        "missing_next_step",
    )
