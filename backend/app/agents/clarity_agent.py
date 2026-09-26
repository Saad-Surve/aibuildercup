"""Spoken Clarity reviewer (`clarity`)."""

from app.agents.reviewer_base import LlmReviewer
from app.schemas.analysis import AnalysisDimension

FOCUS = """\
You review how effortlessly the spoken audio can be parsed in real time.

WHAT TO EVALUATE:
1. Cognitive Overload: sentences packed with more than two independent clauses that
   force the listener to mentally rewind.
2. Ambiguous Pronoun Anchors: use of "this", "they", or "it" where the antecedent is
   ambiguous.
3. Unframed Jargon: domain terms introduced without a brief conversational analogy.
4. Disjointed Procedural Steps: instructions where step 2 assumes information not yet
   provided.

CRITICAL DISTINCTION:
Spoken dialogue is not written prose. Short fragments, pauses, and rhetorical questions
are positive clarity aids on video. Flag cognitive confusion, not colloquial sentence
structure.

findingType vocabulary (severity in brackets):
  clear_breakdown           [none]   an exceptional, easy-to-follow explanation (score 5)
  dense_clause_overload     [medium]
  ambiguous_referent        [medium]
  unexplained_jargon        [medium, high]
  missing_prerequisite_step [high]"""


class ClarityReviewer(LlmReviewer):
    dimension = AnalysisDimension.clarity
    focus = FOCUS
    finding_types = (
        "clear_breakdown",
        "dense_clause_overload",
        "ambiguous_referent",
        "unexplained_jargon",
        "missing_prerequisite_step",
    )
