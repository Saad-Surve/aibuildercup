"""Legal and Safety reviewer (`legal_safety`)."""

from app.agents.reviewer_base import LlmReviewer
from app.schemas.analysis import AnalysisDimension

FOCUS = """\
You review legal and safety risk in the spoken content.

Flag: defamation (naming a person or company with an accusation); medical, legal, or
financial advice given as instruction; dangerous or illegal acts described as
doable; copyright problems (quoting lyrics, readings, or other people's work at
length); personal data of private individuals; information about minors; promotional
claims that are not disclosed as such; platform-policy violations (harassment, hate,
shocking content).

Be conservative. If the risk depends on facts you cannot check, use findingType
"needs_verification" rather than clearing it. Only report a strength (severity "none",
score 5) where the stretch handles a sensitive topic demonstrably well.

findingType vocabulary (severity in brackets):
  safe_handling            [none]   an exceptional, careful treatment (score 5)
  needs_verification       [low, medium]
  defamation_risk          [high, critical]
  professional_advice      [medium, high]
  dangerous_instruction    [high, critical]
  copyright_risk           [medium, high]
  privacy_risk             [high, critical]
  undisclosed_promotion    [medium]
  policy_risk              [medium, high]"""


class LegalSafetyReviewer(LlmReviewer):
    dimension = AnalysisDimension.legal_safety
    focus = FOCUS
    finding_types = (
        "safe_handling",
        "needs_verification",
        "defamation_risk",
        "professional_advice",
        "dangerous_instruction",
        "copyright_risk",
        "privacy_risk",
        "undisclosed_promotion",
        "policy_risk",
    )
