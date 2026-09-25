"""Visual Accessibility reviewer (`visual_accessibility`)."""

from app.agents.reviewer_base import LlmReviewer
from app.schemas.analysis import AnalysisDimension

FOCUS = """\
You review how accessible the content is to someone who cannot see the video well.

Check: information that is only shown and never said; gestures, on-screen text, or
"as you can see here" with nothing spoken to replace it; colour as the only channel
for meaning; anything that would need an audio description track; audio cues with no
spoken equivalent.

You are reviewing the transcript only, so judge what the spoken track is missing, not
what the video may happen to contain. Where the risk depends on the visuals, use
findingType "needs_visual_review" instead of guessing.

findingType vocabulary: unsaid_visual, pointing_reference, colour_only_cue,
missing_description, needs_visual_review, strength."""


class VisualAccessibilityReviewer(LlmReviewer):
    dimension = AnalysisDimension.visual_accessibility
    focus = FOCUS
