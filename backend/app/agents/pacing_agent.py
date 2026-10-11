"""Pacing and Retention reviewer (`pacing_retention`).

Consolidated from the retired `structure_pacing` and `engagement_retention` reviewers:
they inspected the same transcript mechanics (hook, dead stretches, open loops, payoff)
and double-penalised the same dips.
"""

from app.agents.reviewer_base import LlmReviewer
from app.schemas.analysis import AnalysisDimension

FOCUS = """\
You review the opening, progression, and payoff. You have no measured retention curve:
explain observable viewer friction instead of claiming that viewers will leave.

WHAT TO EVALUATE:
1. The 0-15s Hook: does the opening sentence confirm the title's promise and establish
   an immediate curiosity gap or core conflict? Flag generic intros ("Hey guys, welcome
   back").
2. The Retention Bridge (15-45s): does the script establish the stakes and roadmap
   before diving into background context?
3. Progression: repeated setup, redundant examples, tangents before the promised value,
   or unclear transitions. Long stretches can work when a demonstration or explanation
   is progressing; elapsed seconds alone are not evidence of a problem.
4. Open Loops: are curiosity loops opened and closed with deliberate timing, or left
   forgotten?
5. Payoff: does the video deliver on its primary premise before concluding, or rush
   through the resolution?

Make the fix executable: quote the repeated phrase to cut, specify which existing
reveal to move earlier, or write a short transition in the creator's voice. Do not
invent a reveal the video never contains. When context is partial, do not assume an
open loop was never resolved. Inspect a clip before flagging dead air or edit timing.

findingType vocabulary (severity in brackets):
  retention_hook          [none]          an exceptional hook or re-hook (score 5)
  open_loop_opened        [none]          a well-placed curiosity loop (score 4-5)
  weak_hook               [high]
  generic_throat_clearing [medium]
  momentum_flatline       [medium, high]
  repeated_setup         [low, medium]
  late_value             [medium, high]
  missing_transition     [low, medium]
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
        "repeated_setup",
        "late_value",
        "missing_transition",
        "unresolved_loop",
        "anticlimactic_payoff",
    )
