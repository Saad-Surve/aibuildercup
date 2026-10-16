"""Versioned input for the operator-only creator folder importer."""

from datetime import datetime
from pathlib import PurePosixPath
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.services.paths import safe_segment


class ImportModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ImportCreator(ImportModel):
    name: str = Field(min_length=1, max_length=200)
    bio: str = Field(default="", max_length=5000)
    language: str = Field(default="en", max_length=20)
    links: list[str] = Field(default_factory=list, max_length=20)

    @field_validator("links")
    @classmethod
    def http_links(cls, values: list[str]) -> list[str]:
        from urllib.parse import urlsplit

        if any(
            urlsplit(value).scheme not in {"http", "https"} or not urlsplit(value).hostname
            for value in values
        ):
            raise ValueError("Creator links must be HTTP(S) URLs")
        return values


class ImportItem(ImportModel):
    id: str
    kind: Literal["video", "article", "post"]
    title: str = Field(min_length=1, max_length=500)
    description: str = Field(default="", max_length=10000)
    tags: list[str] = Field(default_factory=list, max_length=50)
    textFile: str | None = None
    thumbnailFile: str | None = None
    mediaFile: str | None = None
    url: str | None = None
    language: str = Field(default="en", max_length=20)
    platform: str = Field(default="unknown", max_length=40)
    contentType: str = Field(default="supplied", max_length=80)
    attribution: str = Field(default="", max_length=200)
    license: str | None = Field(default=None, max_length=120)
    collectionMethod: str = Field(default="supplied", max_length=80)
    fetchedAt: datetime | None = None
    publishedAt: datetime | None = None
    viewCount: int | None = Field(default=None, ge=0)
    likeCount: int | None = Field(default=None, ge=0)
    commentCount: int | None = Field(default=None, ge=0)
    durationSeconds: int | None = Field(default=None, ge=0)

    @field_validator("id")
    @classmethod
    def valid_id(cls, value: str) -> str:
        return safe_segment(value, name="itemId")

    @field_validator("textFile", "thumbnailFile", "mediaFile")
    @classmethod
    def relative_file(cls, value: str | None) -> str | None:
        if value is not None:
            path = PurePosixPath(value)
            if (
                not value
                or path.is_absolute()
                or "\\" in value
                or any(part in {"", ".", ".."} for part in value.split("/"))
            ):
                raise ValueError("Files must be relative paths inside the bundle")
        return value

    @field_validator("publishedAt", "fetchedAt")
    @classmethod
    def aware_date(cls, value: datetime | None) -> datetime | None:
        if value is not None and value.tzinfo is None:
            raise ValueError("publishedAt must include a timezone")
        return value

    @field_validator("url")
    @classmethod
    def http_url(cls, value: str | None) -> str | None:
        if value is not None:
            ImportCreator.http_links([value])
        return value

    @model_validator(mode="after")
    def content_required(self) -> "ImportItem":
        if not any((self.textFile, self.thumbnailFile, self.mediaFile)):
            raise ValueError("Each item requires at least one local file")
        if self.kind != "video" and (not self.textFile or self.mediaFile):
            raise ValueError("Articles/posts require textFile and cannot have mediaFile")
        return self


class ImportMetric(ImportModel):
    metric: str = Field(min_length=1, max_length=100)
    value: float = Field(allow_inf_nan=False)


class ImportBreakdownRow(ImportModel):
    label: str = Field(min_length=1, max_length=200)
    value: float = Field(ge=0, allow_inf_nan=False)


class ImportBreakdown(ImportModel):
    dimension: str = Field(min_length=1, max_length=100)
    rows: list[ImportBreakdownRow] = Field(default_factory=list, max_length=100)


class ImportAudience(ImportModel):
    periodDays: int = Field(default=28, ge=1, le=3650)
    summary: list[ImportMetric] = Field(default_factory=list, max_length=50)
    demographics: ImportBreakdown | None = None
    trafficSources: ImportBreakdown | None = None


class CreatorImportManifest(ImportModel):
    schemaVersion: Literal[1] = 1
    bundleId: str
    creator: ImportCreator
    audience: ImportAudience | None = None
    items: list[ImportItem] = Field(min_length=1, max_length=100)

    @field_validator("bundleId")
    @classmethod
    def valid_id(cls, value: str) -> str:
        return safe_segment(value, name="bundleId")

    @model_validator(mode="after")
    def unique_items(self) -> "CreatorImportManifest":
        if len({item.id for item in self.items}) != len(self.items):
            raise ValueError("Item ids must be unique")
        return self
