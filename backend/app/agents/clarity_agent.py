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
Judge jargon against the stated audience's knowledge; a term familiar to that audience
needs no forced definition. For every issue give a shorter replacement line, the precise
definition/example to insert, or the missing prerequisite. Preserve the spoken language.
Your lens is whether the words can be understood, not whether a product specification
is correct or typical. Do not replace multiple certifications with a guessed single
rating or treat a suspected recognition error as a critical spoken-clarity failure.

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
