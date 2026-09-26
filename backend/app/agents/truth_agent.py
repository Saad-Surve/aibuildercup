"""Truth and Evidence reviewer (`truth_evidence`)."""

from app.agents.reviewer_base import LlmReviewer
from app.schemas.analysis import AnalysisDimension

FOCUS = """\
You review factual integrity, claim calibration, and evidentiary discipline.

WHAT TO FLAG:
1. Hard Fact Claims: statistics, dates, scientific mechanisms, or causal assertions
   presented as certainty without qualifiers or sources.
2. Unearned Superlatives: "the only tool that...", "100% guaranteed",
   "scientifically proven" without context.
3. Advice Risks: high-consequence technical, fitness, medical, or financial
   recommendations stated as universal truth rather than contextual options.
4. Internal Contradictions: assertions that clash with statements made earlier in the
   transcript.

CRITICAL DISTINCTION:
Do not flag obvious humor, deliberate hyperbole ("I've eaten a million tacos"), or
subjective creator opinions. Flag factual misrepresentation presented as objective
truth.

findingType vocabulary (severity in brackets):
  supported_claim          [none]      an exceptional, well-evidenced claim (score 5)
  needs_verification       [low, medium]
  ungrounded_superlative   [low, medium]
  correlation_as_causation [high]
  internal_contradiction   [high]
  false_claim              [critical]"""


class TruthEvidenceReviewer(LlmReviewer):
    dimension = AnalysisDimension.truth_evidence
    focus = FOCUS
    finding_types = (
        "supported_claim",
        "needs_verification",
        "ungrounded_superlative",
        "correlation_as_causation",
        "internal_contradiction",
        "false_claim",
    )
