"""Clarity reviewer (`clarity`)."""

from app.agents.reviewer_base import LlmReviewer
from app.schemas.analysis import AnalysisDimension

FOCUS = """\
You review how easy the spoken content is to understand on first listen.

Look for: undefined jargon and acronyms; words with more than one meaning used
without disambiguation; pronouns with no clear referent; sentences that need a second
listen; abstractions with no concrete example; instructions whose steps are out of
order or missing; explanations that skip the one step the audience needs most.

Do not flag a difficult idea that is explained well - difficulty is not the same as
unclear. Mark clear teaching with severity "none" so the heatmap shows the good
stretches too.

findingType vocabulary: jargon, ambiguity, missing_definition, missing_example,
run_on, unclear_referent, skipped_step, strength."""


class ClarityReviewer(LlmReviewer):
    dimension = AnalysisDimension.clarity
    focus = FOCUS
