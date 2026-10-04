"""Draft (written content / video script) schemas.

A draft is a versioned document. Each block (a heading, a paragraph, or a script
scene) keeps an ordered list of `versions`; `activeVersionId` picks the one shown.
Every assistant rewrite or alternative becomes another version, so a word, phrase,
or paragraph can all be compared and swapped losslessly. Exports always follow the
active versions.
"""

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field

from app.schemas.connections import (
    AudienceBreakdown,
    ContentStyleSummary,
    MetricValue,
)


class DraftFormat(StrEnum):
    written = "written"
    script = "script"


class DraftBlockType(StrEnum):
    heading = "heading"
    paragraph = "paragraph"


class DraftStatus(StrEnum):
    empty = "empty"
    generating = "generating"
    ready = "ready"
    failed = "failed"


class DraftBrief(BaseModel):
    """The input box that seeds a draft."""

    topic: str = ""
    format: DraftFormat = DraftFormat.written
    audience: str = ""
    tone: str = ""
    platform: str = ""
    language: str = "en"
    instructions: str = ""
    #: Target length hint in words; 0 means "let the model decide".
    targetWords: int = 0


class DraftVersion(BaseModel):
    versionId: str
    text: str
    #: Short human label ("Draft", "Punchier", "Alternative 2").
    label: str = ""
    origin: str = "assistant"
    createdAt: datetime


class DraftBlock(BaseModel):
    blockId: str
    type: DraftBlockType = DraftBlockType.paragraph
    versions: list[DraftVersion] = Field(default_factory=list)
    activeVersionId: str


class DraftMessage(BaseModel):
    messageId: str
    role: str
    content: str
    createdAt: datetime


class DraftSummary(BaseModel):
    """Small denormalised copy kept on the project for list cards."""

    title: str = ""
    preview: str = ""
    wordCount: int = 0
    blockCount: int = 0
    versionCount: int = 0


class Draft(BaseModel):
    projectId: str
    title: str = ""
    status: DraftStatus = DraftStatus.empty
    brief: DraftBrief = Field(default_factory=DraftBrief)
    blocks: list[DraftBlock] = Field(default_factory=list)
    messages: list[DraftMessage] = Field(default_factory=list)
    error: str | None = None
    summary: DraftSummary = Field(default_factory=DraftSummary)
    createdAt: datetime | None = None
    updatedAt: datetime | None = None


class GenerateDraftRequest(BaseModel):
    """Optional overrides for the stored brief; all fields may be omitted."""

    topic: str | None = None
    format: DraftFormat | None = None
    audience: str | None = None
    tone: str | None = None
    platform: str | None = None
    language: str | None = None
    instructions: str | None = None
    targetWords: int | None = None


class SaveDraftRequest(BaseModel):
    """Persist client-side edits: title, block texts, and block ordering."""

    title: str | None = None
    blocks: list[DraftBlock] = Field(default_factory=list)


class AssistMode(StrEnum):
    chat = "chat"
    rewrite = "rewrite"
    alternatives = "alternatives"
    continue_draft = "continue"


class SuggestMode(StrEnum):
    rewrite = "rewrite"
    alternatives = "alternatives"


class SuggestDraftRequest(BaseModel):
    """Ask the writing partner for alternatives to a selected span."""

    text: str = Field(min_length=1, max_length=4000)
    context: str = ""
    mode: SuggestMode = SuggestMode.alternatives
    count: int = Field(default=3, ge=1, le=5)


class SuggestDraftResponse(BaseModel):
    suggestions: list[str] = Field(default_factory=list)


class AssistDraftRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
    #: When set, the instruction is scoped to this block.
    blockId: str | None = None
    mode: AssistMode = AssistMode.chat


class CreatorContextExample(BaseModel):
    """One past video the writer retrieved as style evidence."""

    videoId: str
    title: str = ""
    tags: list[str] = Field(default_factory=list)
    viewCount: int | None = None
    likeCount: int | None = None
    commentCount: int | None = None
    publishedAt: datetime | None = None
    thumbnailUrl: str | None = None
    transcriptExcerpt: str | None = None


class CreatorContextAudience(BaseModel):
    """The audience slice sent to the writer."""

    periodDays: int = 28
    summary: list[MetricValue] = Field(default_factory=list)
    demographics: AudienceBreakdown | None = None
    trafficSources: AudienceBreakdown | None = None


class CreatorContext(BaseModel):
    """What the last draft generation pulled from the creator's channel (for the UI)."""

    available: bool = False
    generatedAt: datetime | None = None
    connectionId: str | None = None
    connectionDisplayName: str | None = None
    style: ContentStyleSummary | None = None
    examples: list[CreatorContextExample] = Field(default_factory=list)
    audience: CreatorContextAudience | None = None
