from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class OnboardingStatus(StrEnum):
    not_started = "not_started"
    in_progress = "in_progress"
    completed = "completed"


class OnboardingStep(BaseModel):
    step: str = Field(min_length=1, max_length=64)
    answers: dict[str, Any] = Field(default_factory=dict)


class OnboardingState(BaseModel):
    status: OnboardingStatus
    currentStep: str | None = None
    answers: dict[str, Any] = Field(default_factory=dict)


class OnboardingResearchRequest(BaseModel):
    """The creator's public profile links, used to prefill the persona form."""

    links: list[str] = Field(min_length=1, max_length=10)


class ResearchSource(BaseModel):
    """One web source the research call used, for the UI's provenance list."""

    title: str = ""
    url: str = ""


class OnboardingResearch(BaseModel):
    """A grounded research result that prefills the onboarding answers."""

    #: The full merged answers after research (ready to load straight into the form).
    answers: dict[str, Any] = Field(default_factory=dict)
    sources: list[ResearchSource] = Field(default_factory=list)
    #: Search queries the grounded model ran.
    queries: list[str] = Field(default_factory=list)
    #: Google-provided Search Suggestions HTML; must be rendered exactly as returned.
    searchSuggestions: str = ""
