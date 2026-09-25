"""Engagement and Retention reviewer (`engagement_retention`)."""

from app.agents.reviewer_base import LlmReviewer
from app.schemas.analysis import AnalysisDimension

FOCUS = """\
You review where a viewer is likely to drop off.

Use the timings you are given. Flag: stretches with no new information or tension; a
promise made and not paid off quickly; filler, throat-clearing, and restated points;
moments where a viewer would feel safe leaving; missing re-hooks after a long stretch;
open loops left dangling too long.

Reward the opposite with severity "none": re-hooks, pattern interrupts, and moments
that earn the next minute.

findingType vocabulary: dropoff_risk, filler, dangling_open_loop, missing_rehook,
repeated_point, retention_hook."""


class EngagementRetentionReviewer(LlmReviewer):
    dimension = AnalysisDimension.engagement_retention
    focus = FOCUS
