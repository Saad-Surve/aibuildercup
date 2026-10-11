"""Grounded visual inserts and editable YouTube metadata."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


def youtube_tags_size(tags: list[str]) -> int:
    return sum(len(tag) + (2 if " " in tag else 0) for tag in tags) + max(0, len(tags) - 1)


class PackagingBrief(BaseModel):
    model_config = ConfigDict(extra="forbid")
    brief: str = Field(default="", max_length=2000)
    useCreatorHistory: bool = True


class PackagingAccepted(BaseModel):
    jobId: str
    status: str


class ListingFields(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str = Field(min_length=1, max_length=100)
    description: str = Field(default="", max_length=5000)
    tags: list[str] = Field(
        default_factory=list,
        max_length=30,
        description="YouTube tags: at most 100 characters per tag and 500 total, including "
        "separators and quotes around tags containing spaces.",
    )

    @field_validator("title")
    @classmethod
    def clean_title(cls, value: str) -> str:
        value = value.strip()
        if not value or "<" in value or ">" in value:
            raise ValueError("Enter a title without angle brackets.")
        return value

    @field_validator("description")
    @classmethod
    def clean_description(cls, value: str) -> str:
        if "<" in value or ">" in value:
            raise ValueError("YouTube descriptions cannot contain angle brackets.")
        return value

    @field_validator("tags")
    @classmethod
    def clean_tags(cls, values: list[str]) -> list[str]:
        tags = list(dict.fromkeys(v.strip() for v in values if v.strip()))
        if any(len(v) > 100 for v in tags) or youtube_tags_size(tags) > 500:
            raise ValueError("YouTube tags must fit within 500 characters including separators.")
        return tags


class PackagingEvidence(BaseModel):
    title: str
    url: str | None = None


class PackagingListing(ListingFields):
    model_config = ConfigDict(extra="ignore")
    status: Literal["queued", "generating", "ready", "failed"]
    sourceAssetId: str
    transcriptId: str
    titleOptions: list[str] = Field(default_factory=list, max_length=3)
    rationale: str = ""
    creatorHistoryUsed: bool = False
    evidence: list[PackagingEvidence] = Field(default_factory=list)
    jobId: str | None = None
    error: str | None = None
    updatedAt: datetime
    stale: bool = False


class ChartDatum(BaseModel):
    label: str = Field(min_length=1, max_length=50)
    value: float = Field(ge=0, le=1_000_000_000, allow_inf_nan=False)
    sourceQuote: str = Field(min_length=1, max_length=600)
    sourceTimestampMs: int = Field(
        default=0, ge=0, description="Source segment start for this value; derived by the server."
    )


class VisualInsertIdea(BaseModel):
    kind: Literal["chart", "callout", "broll"]
    headline: str = Field(min_length=1, max_length=90)
    body: str = Field(default="", max_length=250)
    rationale: str = Field(min_length=1, max_length=1000)
    sourceStartMs: int = Field(ge=0)
    sourceEndMs: int = Field(ge=0)
    sourceQuote: str = Field(min_length=1, max_length=600)
    prompt: str = Field(default="", max_length=2000)
    chart: list[ChartDatum] = Field(default_factory=list, max_length=5)
    chartUnit: str = Field(default="", max_length=35)


class VisualStyle(BaseModel):
    summary: str = Field(min_length=1, max_length=800)
    palette: str = Field(min_length=1, max_length=400)
    lighting: str = Field(min_length=1, max_length=400)
    composition: str = Field(min_length=1, max_length=400)
    texture: str = Field(min_length=1, max_length=400)
    motion: str = Field(min_length=1, max_length=400)
    setting: str = Field(min_length=1, max_length=400)


class VisualInsert(VisualInsertIdea):
    visualStyle: VisualStyle | None = Field(
        default=None, description="Observed look of the source footage near this insert."
    )
    generationMode: Literal["text-to-video", "image-to-video"] = "text-to-video"
    styleReferenceTimestampMs: int | None = Field(default=None, ge=0)
    styleReferenceUrl: str | None = Field(
        default=None,
        description="Signed source-frame preview; only image-to-video sends it to Veo.",
    )
    conditioningReason: str = Field(default="", max_length=800)
    insertId: str
    status: Literal["suggested", "queued", "rendering", "ready", "failed"]
    sourceAssetId: str
    transcriptId: str
    durationSeconds: Literal[6] = 6
    aspectRatio: Literal["16:9", "9:16"] = "16:9"
    canRetry: bool = Field(
        default=True,
        description="False for terminal or ambiguous video failures. Resumable operations reuse "
        "the submitted prompt and aspect.",
    )
    estimatedCostUsd: float = 0
    jobId: str | None = None
    previewUrl: str | None = None
    error: str | None = None
    stale: bool = False
    createdAt: datetime


class VisualInsertList(BaseModel):
    items: list[VisualInsert]
    suggestionJobId: str | None = None
    paidRendersRemaining: int = Field(ge=0)


class RenderVisualInsertRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    prompt: str | None = Field(default=None, min_length=1, max_length=2000)
    aspectRatio: Literal["16:9", "9:16"] = "16:9"
    allowPaidGeneration: bool = False
