"""Channel drop-off calibration; deliberately separate from public model evaluation."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class CalibrateInterestRequest(BaseModel):
    connectionId: str = Field(min_length=1, max_length=128)


class CreatorInterestBucket(BaseModel):
    bucket: Literal["short", "long"]
    videos: int = 0
    views: int = 0
    creatorWeight: float = Field(default=0, ge=0, le=1)


class CreatorInterestCalibration(BaseModel):
    status: Literal["not_started", "calibrating", "ready", "insufficient_data", "failed"]
    connectionId: str | None = None
    channelName: str | None = None
    channelId: str | None = None
    videos: int = 0
    views: int = 0
    scannedVideos: int = 0
    apiRequests: int = 0
    buckets: list[CreatorInterestBucket] = Field(default_factory=list)
    reason: str | None = None
    attemptedAt: datetime | None = None
    calibratedAt: datetime | None = None
    nextAllowedAt: datetime | None = None
    startDate: str | None = None
    endDate: str | None = None
    methodVersion: str = "creator-position-v1"


class InterestBaselineSource(BaseModel):
    source: Literal["generic", "creator"] = "generic"
    reason: str | None = None
    connectionId: str | None = None
    channelName: str | None = None
    calibratedAt: datetime | None = None
    videos: int = 0
    views: int = 0
    creatorWeight: float = 0
    bucket: Literal["short", "long"] | None = None
