"""Structure and Pacing reviewer (`structure_pacing`)."""

from app.agents.reviewer_base import LlmReviewer
from app.schemas.analysis import AnalysisDimension

FOCUS = """\
You review the shape and the tempo of the content.

Check: is there a hook in the first fifteen seconds that says why the viewer should
stay? Is the order of ideas the order a learner needs? Are there digressions that
break the thread? Does each section earn its length? Is there a payoff or a real
ending, or does it just stop? Are there dead stretches, repeated points, or rushed
sections that needed room?

Judge pacing against the timings you are given: a long monologue with no turn and a
string of rapid topic switches are both pacing problems.

findingType vocabulary: weak_hook, missing_hook, digression, repetition, slow_section,
rushed_section, missing_payoff, abrupt_end, good_flow."""


class StructurePacingReviewer(LlmReviewer):
    dimension = AnalysisDimension.structure_pacing
    focus = FOCUS
