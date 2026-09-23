from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field


class AssetStatus(StrEnum):
    pending = "pending"
    uploading = "uploading"
    uploaded = "uploaded"
    processing = "processing"
    ready = "ready"
    failed = "failed"
    deleted = "deleted"


class AssetType(StrEnum):
    source_video = "source_video"
    audio = "audio"
    frame = "frame"
    clip = "clip"
    thumbnail = "thumbnail"
    caption = "caption"
    export = "export"


class CreateUploadSession(BaseModel):
    fileName: str = Field(min_length=1, max_length=255)
    contentType: str = Field(min_length=1, max_length=128)
    sizeBytes: int = Field(gt=0)


class UploadSession(BaseModel):
    assetId: str
    storagePath: str
    uploadUrl: str
    expiresAt: datetime
    requiredHeaders: dict[str, str]


class Asset(BaseModel):
    assetId: str
    projectId: str
    type: AssetType
    status: AssetStatus
    storagePath: str
    mimeType: str
    sizeBytes: int
    durationMs: int | None = None
    createdAt: datetime
    updatedAt: datetime


class AssetList(BaseModel):
    items: list[Asset]


class DownloadUrl(BaseModel):
    url: str
    expiresAt: datetime
