from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field

from app.schemas.rough_cut import RoughCutMetadata


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
    #: Source-video revision number; None for non-source assets and legacy sources.
    revision: int | None = None
    roughCut: RoughCutMetadata | None = None
    createdAt: datetime
    updatedAt: datetime


class AssetList(BaseModel):
    items: list[Asset]


class Revision(BaseModel):
    revision: int
    assetId: str
    status: AssetStatus
    mimeType: str
    sizeBytes: int
    durationMs: int | None = None
    storagePath: str
    isActive: bool
    #: The newest transcript built from this revision, and how many reviews it has.
    transcriptId: str | None = None
    transcriptVersion: int | None = None
    analysisRunCount: int = 0
    createdAt: datetime


class RevisionList(BaseModel):
    items: list[Revision]


class RevisionActivation(BaseModel):
    assetId: str
    revision: int
    #: The transcript made active, or None when a fresh one had to be generated.
    transcriptId: str | None = None
    #: The queued transcribe job when the revision had no transcript yet.
    jobId: str | None = None


class DownloadUrl(BaseModel):
    url: str
    expiresAt: datetime
