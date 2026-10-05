"""Grounded creator research for onboarding.

The creator pastes links to their public profiles (YouTube, Instagram, X, ...). One grounded
Gemini call (Grounding with Google Search) drafts the onboarding answers, so the persona form
arrives prefilled instead of asking the creator to type everything. The links, the grounding
sources, and the queries are stored on the user document under `onboarding`, inside
`users/{uid}`, and are therefore covered by the account delete path.

Grounding with Google Search obliges the client to render the Search Suggestions HTML exactly
as returned and to show the sources; the API returns both, and the web client renders them.
"""

import json
import logging
from typing import Any
from urllib.parse import urlparse

from app.config import Settings
from app.errors import BadRequestError, ForbiddenError
from app.providers.base import GroundingInfo, LlmProvider
from app.schemas.onboarding import (
    OnboardingResearch,
    OnboardingResearchRequest,
    ResearchSource,
)
from app.services.user_service import UserService

logger = logging.getLogger(__name__)

RESEARCH_PROMPT_VERSION = "persona-research-v1"

RESEARCH_SYSTEM = (
    "You are a creator strategist doing onboarding research. The creator gave you links to "
    "their public profiles. Use Google Search to read those profiles and what the web says "
    "about them, then draft their creator persona answers. Rules: only use information you "
    "actually found on the linked profiles or the web; never invent facts, numbers, or "
    "audience data. Infer topics, formats, tone, audience, and language from real video "
    "titles, descriptions, captions, and public bio text. Leave a field empty when the "
    "evidence does not support it. Return the sources you relied on with their exact URLs. "
    "Choose category and language values only from the allowed values in the schema."
)

# Allowed values mirror `web/src/lib/onboarding.ts`. The model is constrained by the schema
# enum, but the output is re-validated here so only known values can reach the form.
_LANGUAGE_VALUES = ("en", "hi", "mr", "ta", "te", "bn", "es")
_TOPIC_VALUES = (
    "finance",
    "career",
    "technology",
    "education",
    "health_fitness",
    "lifestyle",
    "gaming",
    "travel",
    "food",
    "business",
    "culture",
    "entertainment",
)
_FORMAT_VALUES = (
    "talking_head",
    "tutorial",
    "vlog",
    "interview",
    "review",
    "listicle",
    "documentary",
    "shorts",
)
_LENGTH_VALUES = ("under_5", "5_15", "15_30", "over_30")
_KNOWLEDGE_VALUES = ("beginner", "intermediate", "advanced", "mixed")
_TONE_VALUES = (
    "direct",
    "friendly",
    "analytical",
    "motivational",
    "humorous",
    "calm",
    "authoritative",
)
_HOOK_VALUES = ("question", "bold_claim", "story", "statistic")
_CAPTION_VALUES = ("minimal", "standard", "verbose")
_PLATFORM_VALUES = (
    "youtube",
    "youtube_shorts",
    "instagram",
    "facebook",
    "linkedin",
    "tiktok",
    "x",
)

_TEXT_FIELDS = (
    "creatorName",
    "location",
    "bio",
    "audience",
    "audienceLocation",
    "primaryGoal",
    "wordsToAvoid",
    "regionalPreferences",
)
_SINGLE_FIELDS: dict[str, tuple[str, ...]] = {
    "primaryLanguage": _LANGUAGE_VALUES,
    "typicalLength": _LENGTH_VALUES,
    "knowledgeLevel": _KNOWLEDGE_VALUES,
    "hookStyle": _HOOK_VALUES,
    "captionPreferences": _CAPTION_VALUES,
}
_MULTI_FIELDS: dict[str, tuple[str, ...]] = {
    "topics": _TOPIC_VALUES,
    "contentFormats": _FORMAT_VALUES,
    "tone": _TONE_VALUES,
    "platforms": _PLATFORM_VALUES,
}

# Host suffix -> platform value. Used as a reliable signal in addition to the model's guess.
_HOST_PLATFORMS = (
    ("youtube.com", "youtube"),
    ("youtu.be", "youtube"),
    ("instagram.com", "instagram"),
    ("facebook.com", "facebook"),
    ("fb.com", "facebook"),
    ("fb.watch", "facebook"),
    ("twitter.com", "x"),
    ("x.com", "x"),
    ("tiktok.com", "tiktok"),
    ("linkedin.com", "linkedin"),
)

_MAX_SOURCES = 8


def _research_schema() -> dict[str, Any]:
    def enum(values: tuple[str, ...]) -> dict[str, Any]:
        return {"type": "string", "enum": list(values)}

    def enum_list(values: tuple[str, ...]) -> dict[str, Any]:
        return {"type": "array", "items": enum(values)}

    return {
        "type": "object",
        "properties": {
            "creatorName": {"type": "string"},
            "location": {"type": "string"},
            "bio": {"type": "string"},
            "primaryLanguage": enum(_LANGUAGE_VALUES),
            "topics": enum_list(_TOPIC_VALUES),
            "contentFormats": enum_list(_FORMAT_VALUES),
            "typicalLength": enum(_LENGTH_VALUES),
            "audience": {"type": "string"},
            "audienceLocation": {"type": "string"},
            "knowledgeLevel": enum(_KNOWLEDGE_VALUES),
            "primaryGoal": {"type": "string"},
            "tone": enum_list(_TONE_VALUES),
            "wordsToAvoid": {"type": "string"},
            "hookStyle": enum(_HOOK_VALUES),
            "captionPreferences": enum(_CAPTION_VALUES),
            "regionalPreferences": {"type": "string"},
            "platforms": enum_list(_PLATFORM_VALUES),
            "sources": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "title": {"type": "string"},
                        "url": {"type": "string"},
                    },
                    "required": ["title", "url"],
                },
            },
        },
        "required": ["sources"],
    }


def _normalize_links(links: list[str], max_links: int) -> list[str]:
    """Trim, add a missing scheme, and reject anything that is not an http(s) URL."""
    normalized: list[str] = []
    for raw in links:
        text = raw.strip()
        if not text:
            continue
        if "://" not in text:
            text = f"https://{text.lstrip('/')}"
        parsed = urlparse(text)
        if (
            parsed.scheme not in ("http", "https")
            or not parsed.netloc
            or any(char.isspace() for char in parsed.netloc)
        ):
            raise BadRequestError(
                f"Not a valid profile link: {raw}", code="INVALID_PROFILE_LINK"
            )
        canonical = parsed._replace(fragment="").geturl()
        if canonical not in normalized:
            normalized.append(canonical)
    if not normalized:
        raise BadRequestError(
            "At least one profile link is required", code="INVALID_PROFILE_LINK"
        )
    return normalized[:max_links]


def infer_platforms(links: list[str]) -> list[str]:
    """Map profile hostnames to platform values, in the order the links were given."""
    found: list[str] = []
    for link in links:
        host = (urlparse(link).hostname or "").lower().removeprefix("www.")
        for suffix, platform in _HOST_PLATFORMS:
            if host == suffix or host.endswith(f".{suffix}"):
                if platform not in found:
                    found.append(platform)
                break
    return found


def _clean_answers(raw: dict[str, Any]) -> dict[str, Any]:
    """Keep only known answer fields with valid values; drop everything else."""
    answers: dict[str, Any] = {}
    for key in _TEXT_FIELDS:
        value = raw.get(key)
        if isinstance(value, str) and value.strip():
            answers[key] = value.strip()
    for key, allowed in _SINGLE_FIELDS.items():
        value = raw.get(key)
        if isinstance(value, str) and value in allowed:
            answers[key] = value
    for key, allowed in _MULTI_FIELDS.items():
        value = raw.get(key)
        if not isinstance(value, list):
            continue
        chosen: list[str] = []
        for item in value:
            if isinstance(item, str) and item in allowed and item not in chosen:
                chosen.append(item)
        if chosen:
            answers[key] = chosen
    return answers


def _clean_sources(
    raw: Any, grounding: GroundingInfo | None
) -> list[ResearchSource]:
    """Merge model-emitted sources with the provider's grounding chunks, deduped by URL."""
    sources: list[ResearchSource] = []
    seen: set[str] = set()

    def add(title: str, url: str) -> None:
        url = url.strip()
        if not url.startswith(("http://", "https://")) or url in seen:
            return
        seen.add(url)
        sources.append(ResearchSource(title=title.strip() or url, url=url))

    if isinstance(raw, list):
        for item in raw:
            if isinstance(item, dict):
                add(str(item.get("title") or ""), str(item.get("url") or ""))
    if grounding is not None:
        for source in grounding.sources:
            add(source.title, source.uri)
    return sources[:_MAX_SOURCES]


class PersonaResearchService:
    def __init__(
        self,
        *,
        llm: LlmProvider,
        users: UserService,
        settings: Settings,
    ) -> None:
        self.llm = llm
        self.users = users
        self.settings = settings

    async def research(
        self, owner_uid: str, request: OnboardingResearchRequest
    ) -> OnboardingResearch:
        if not self.settings.onboarding_research_enabled:
            raise ForbiddenError(
                "Creator research is disabled", code="RESEARCH_DISABLED"
            )

        links = _normalize_links(request.links, self.settings.onboarding_research_max_links)
        inferred = infer_platforms(links)
        user = json.dumps(
            {"links": links, "detectedPlatforms": inferred}, ensure_ascii=False
        )
        completion = await self.llm.complete_json(
            model=self.settings.model_research,
            prompt_version=RESEARCH_PROMPT_VERSION,
            system=RESEARCH_SYSTEM,
            user=user,
            schema=_research_schema(),
            grounding=True,
        )

        raw = completion.data
        answers = _clean_answers(raw)
        # The detected platforms come from the links themselves, so they are trustworthy even
        # when the model returns nothing; union them with whatever the model found.
        model_platforms = answers.get("platforms") or []
        platforms = [p for p in inferred if p not in model_platforms] + list(model_platforms)
        if platforms:
            answers["platforms"] = platforms

        grounding = completion.grounding
        sources = _clean_sources(raw.get("sources"), grounding)
        queries = list(grounding.queries) if grounding else []
        suggestions = grounding.search_suggestions_html if grounding else ""

        state = self.users.save_onboarding_research(
            owner_uid,
            links=links,
            answers=answers,
            sources=[source.model_dump() for source in sources],
            queries=queries,
            search_suggestions=suggestions,
            model=self.settings.model_research,
        )
        return OnboardingResearch(
            answers=state.answers,
            sources=sources,
            queries=queries,
            searchSuggestions=suggestions,
        )
