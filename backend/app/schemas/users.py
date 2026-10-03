from pydantic import BaseModel, Field


class Preferences(BaseModel):
    timezone: str = "UTC"
    defaultLanguage: str = "en"


class AvatarState(BaseModel):
    """Humation avatar: a deterministic seed plus optional per-slot overrides.

    Stored inline on the user document (`users/{uid}.avatar`), so it follows the user
    across browsers and needs no object storage. Parts are addressed by selection slot
    (`head`, `hair`, ...); colors are CSS variables keyed by color slot.
    """

    seed: str | None = None
    selections: dict[str, str] = Field(default_factory=dict)
    colors: dict[str, str] = Field(default_factory=dict)


class Me(BaseModel):
    uid: str
    displayName: str | None = None
    email: str | None = None
    onboardingCompleted: bool
    personaVersion: int | None = None
    preferences: Preferences = Field(default_factory=Preferences)
    avatar: AvatarState | None = None
    #: True for the read-only demo account. The web client uses it to disable every
    #: mutating control; the API enforces read-only independently of this flag.
    readOnly: bool = False
