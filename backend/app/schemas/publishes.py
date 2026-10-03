"""Publishing a finished project to a connected platform.

One *publish* is one upload attempt: it picks a video (the original, a burned-caption render, or
a localized dub), a thumbnail, and a caption track, then pushes all three to the target channel.
Records live under the project subtree, so the recursive project/account delete covers them.
"""

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field, field_validator


class PublishSourceKind(StrEnum):
    #: The project's active source video.
    source = "source"
    #: A ready caption render (the burned-in MP4).
    captionRender = "captionRender"
    #: A ready localization/dub.
    localization = "localization"


class PublishVideoSource(BaseModel):
    kind: PublishSourceKind = PublishSourceKind.source
    #: `captionRenderId` or `localizationId`; omitted for `source`.
    id: str | None = Field(default=None, max_length=200)


class PublishCaptionFormat(StrEnum):
    srt = "srt"
    vtt = "vtt"
    none = "none"


class PublishVisibility(StrEnum):
    private = "private"
    unlisted = "unlisted"
    public = "public"


class PublishThumbnail(BaseModel):
    thumbnailId: str = Field(max_length=200)
    #: 1-based version; omit for the concept's latest generated image.
    version: int | None = Field(default=None, ge=1)


class PublishRequest(BaseModel):
    connectionId: str = Field(max_length=200)
    video: PublishVideoSource = Field(default_factory=PublishVideoSource)
    title: str = Field(min_length=1, max_length=100)
    description: str = Field(default="", max_length=5000)
    tags: list[str] = Field(default_factory=list)
    #: YouTube category id; 22 is "People & Blogs".
    categoryId: str = "22"
    privacyStatus: PublishVisibility = PublishVisibility.private
    #: YouTube requires this flag; a false value is the creator affirming "not made for kids".
    madeForKids: bool = False
    notifySubscribers: bool = True
    captionFormat: PublishCaptionFormat = PublishCaptionFormat.srt
    captionLanguage: str = Field(default="en", max_length=35)
    captionName: str = Field(default="English", max_length=150)
    thumbnail: PublishThumbnail | None = None
    #: When set with `privacyStatus = private`, YouTube schedules the video to go public then.
    publishAt: datetime | None = None

    @field_validator("tags")
    @classmethod
    def _clean_tags(cls, tags: list[str]) -> list[str]:
        cleaned = [tag.strip() for tag in tags if tag and tag.strip()]
        # YouTube rejects a video whose combined tags exceed 500 characters.
        if sum(len(tag) for tag in cleaned) > 500:
            raise ValueError("Tags are limited to 500 characters in total.")
        return cleaned


class PublishStatus(StrEnum):
    queued = "queued"
    uploading = "uploading"
    processing = "processing"
    published = "published"
    failed = "failed"


class Publish(BaseModel):
    publishId: str
    projectId: str
    connectionId: str
    #: Denormalised so the UI can show the channel without a second request.
    connectionDisplayName: str | None = None
    platform: str = "youtube"
    status: PublishStatus
    video: PublishVideoSource
    title: str
    description: str = ""
    tags: list[str] = Field(default_factory=list)
    categoryId: str = "22"
    privacyStatus: PublishVisibility = PublishVisibility.private
    madeForKids: bool = False
    notifySubscribers: bool = True
    captionFormat: PublishCaptionFormat = PublishCaptionFormat.srt
    captionLanguage: str = "en"
    captionName: str = "English"
    thumbnailId: str | None = None
    thumbnailVersion: int | None = None
    youtubeVideoId: str | None = None
    youtubeUrl: str | None = None
    #: 0-100 upload progress reported by the resumable upload.
    uploadProgress: int = 0
    #: Short, ordered human-readable steps ("Uploading video", "Setting thumbnail", ...).
    steps: list[str] = Field(default_factory=list)
    jobId: str | None = None
    error: dict[str, Any] | None = None
    createdAt: datetime
    updatedAt: datetime


class PublishList(BaseModel):
    items: list[Publish]


class PublishAccepted(BaseModel):
    publishId: str
    jobId: str
    status: str
