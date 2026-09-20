from pydantic import BaseModel, Field


class Preferences(BaseModel):
    timezone: str = "UTC"
    defaultLanguage: str = "en"


class Me(BaseModel):
    uid: str
    displayName: str | None = None
    email: str | None = None
    onboardingCompleted: bool
    personaVersion: int | None = None
    preferences: Preferences = Field(default_factory=Preferences)
