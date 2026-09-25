"""Platform Fit reviewer (`platform_fit`)."""

from app.agents.reviewer_base import LlmReviewer
from app.schemas.analysis import AnalysisDimension

FOCUS = """\
You review how well the content fits the target platform named in the task.

Consider: an opening that matches how that platform's viewers decide to stay or leave;
length and sectioning against that platform's norms; whether the request for
engagement is placed and worded the way the platform expects; whether the content
depends on something the platform will not deliver (for example a silent feed or a
missing visual); whether it reads as native to the platform rather than a repost from
somewhere else.

Do not reward generic "good content" - reward fit. A strong stretch that would
perform better on another platform is not a strength here.

findingType vocabulary: weak_open, wrong_length, off_platform_tone,
engagement_mismatch, needs_visuals, repurposed_feel, good_fit."""


class PlatformFitReviewer(LlmReviewer):
    dimension = AnalysisDimension.platform_fit
    focus = FOCUS
