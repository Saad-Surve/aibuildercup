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
