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
Do not flag a familiar local reference or idiom merely because some other audience
might not know it. Establish the intended audience or localization need from the brief
and persona first. Suggest the actual equivalent or a short explanation, not "localize
this". Do not replace the creator's cultural identity with generic global phrasing.
Natural Hindi-English code-switching, including complete English sentences, is not a
translation problem for a Hinglish audience. Without an explicit destination language
or audience comprehension problem, do not demand pure Hindi or rewrite colloquial phrasing.
This lens covers meaning and conventions, not product specifications or factual accuracy;
leave those to Truth & Evidence. A possible speech-recognition error is not a cultural flaw.
Natural local wording and use of the local currency are ordinary good communication,
not exceptional strengths. Reserve a strength for a specific technique worth repeating.

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
