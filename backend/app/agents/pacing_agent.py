"""Pacing and Retention reviewer (`pacing_retention`).

Consolidated from the retired `structure_pacing` and `engagement_retention` reviewers:
they inspected the same transcript mechanics (hook, dead stretches, open loops, payoff)
and double-penalised the same dips.
"""

from app.agents.reviewer_base import LlmReviewer
from app.schemas.analysis import AnalysisDimension

FOCUS = """\
You review audience retention curves, psychological hooks, open loops, and narrative
rhythm.

WHAT TO EVALUATE:
1. The 0-15s Hook: does the opening sentence confirm the title's promise and establish
   an immediate curiosity gap or core conflict? Flag generic intros ("Hey guys, welcome
   back").
2. The Retention Bridge (15-45s): does the script establish the stakes and roadmap
   before diving into background context?
3. Cognitive Dead Zones: segments exceeding 30-45 seconds with no new insights, tonal
   shifts, or open loops.
4. Open Loops: are curiosity loops opened and closed with deliberate timing, or left
   forgotten?
5. Payoff: does the video deliver on its primary premise before concluding, or rush
   through the resolution?

findingType vocabulary (severity in brackets):
  retention_hook          [none]          an exceptional hook or re-hook (score 5)
  open_loop_opened        [none]          a well-placed curiosity loop (score 4-5)
  weak_hook               [high]
  generic_throat_clearing [medium]
  momentum_flatline       [medium, high]
  unresolved_loop         [medium]
  anticlimactic_payoff    [high]"""


class PacingRetentionReviewer(LlmReviewer):
    dimension = AnalysisDimension.pacing_retention
    focus = FOCUS
    finding_types = (
        "retention_hook",
        "open_loop_opened",
        "weak_hook",
        "generic_throat_clearing",
        "momentum_flatline",
        "unresolved_loop",
        "anticlimactic_payoff",
    )
