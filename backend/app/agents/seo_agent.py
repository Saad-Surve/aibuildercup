"""SEO and Discoverability reviewer (`seo_discoverability`)."""

from app.agents.reviewer_base import LlmReviewer
from app.schemas.analysis import AnalysisDimension

FOCUS = """\
You review how discoverable the content is from the spoken words alone.

Check: is the topic named in plain words a viewer would actually type? Are the key
phrases said out loud early enough to land in the transcript? Are synonyms and question
forms covered ("how do I ...", "what is ...")? Is there anything in the spoken content
that would confuse a search or recommendation system about what this is about?

You are judging the spoken content only. Do not invent a title or a description.

findingType vocabulary: missing_keyphrase, vague_topic, no_question_form,
keyword_stuffing, discoverable_phrase, strength."""


class SeoDiscoverabilityReviewer(LlmReviewer):
    dimension = AnalysisDimension.seo_discoverability
    focus = FOCUS
