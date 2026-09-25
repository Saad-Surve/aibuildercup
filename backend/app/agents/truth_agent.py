"""Truth and Evidence reviewer (`truth_evidence`)."""

from app.agents.reviewer_base import LlmReviewer
from app.schemas.analysis import AnalysisDimension

FOCUS = """\
You review factual accuracy and evidentiary support.

1. Identify every factual claim: statistics, dates, names, causal claims, "studies
   show", superlatives ("the best", "the first"), and instructions presented as safe.
2. For each claim, decide from the transcript alone whether it is supported. You have
   no web access here. A claim that needs an outside source is findingType
   "needs_manual_verification" - never confirm it from model memory.
3. Flag overstatement: hedged truth sold as certainty, correlation sold as causation,
   anecdote sold as data.
4. Flag claims that are wrong on their face or that contradict something else said
   in the same piece.
5. Where a claim is well supported by the surrounding argument, say so with severity
   "none" and quote it, so the good stretches show up on the heatmap.

findingType vocabulary: supported_claim, needs_manual_verification, overstatement,
unsupported_claim, contradiction, incorrect_claim."""


class TruthEvidenceReviewer(LlmReviewer):
    dimension = AnalysisDimension.truth_evidence
    focus = FOCUS
