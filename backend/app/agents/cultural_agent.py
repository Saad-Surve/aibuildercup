"""Cultural and Localization reviewer (`cultural_localization`)."""

from app.agents.reviewer_base import LlmReviewer
from app.schemas.analysis import AnalysisDimension

FOCUS = """\
You review how well the content travels across languages and cultures, with particular
care for Indian English and Indian regional languages (Hindi, Marathi, Tamil, Telugu,
Bengali).

Flag: idioms and wordplay that will not translate ("hit it out of the park", puns);
culture-bound references and examples the target audience will not know; assumptions
about names, food, festivals, currency, schooling, or family structure; a tone that
reads differently in the target culture (for example bluntness that reads as rudeness);
words that are traps when localized; numbers, dates, and units in the wrong convention.

Rate the risk to the intended audience, not to a US audience. A stretch that travels
exceptionally well is a strength (severity "none", score 5).

findingType vocabulary (severity in brackets):
  strength               [none]   an example that travels especially well (score 5)
  untranslatable_idiom   [medium]
  culture_reference      [medium]
  locale_assumption      [medium, high]
  tone_mismatch          [medium]
  translation_trap       [medium, high]
  unit_or_format         [low]"""


class CulturalLocalizationReviewer(LlmReviewer):
    dimension = AnalysisDimension.cultural_localization
    focus = FOCUS
    finding_types = (
        "strength",
        "untranslatable_idiom",
        "culture_reference",
        "locale_assumption",
        "tone_mismatch",
        "translation_trap",
        "unit_or_format",
    )
