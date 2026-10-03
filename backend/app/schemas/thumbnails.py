"""Thumbnail studio schemas.

A *thumbnail concept* is one candidate thumbnail the creator can iterate on. It is grounded in
the video: a planner reads the transcript and the reviewer findings, picks a moment, and writes
a headline plus a rationale that cites the evidence. The image is generated from that plan,
using real frames from the video as references so the creator's likeness survives.

Every edit is additive: a concept holds an append-only list of `ThumbnailVersion`s (mirroring
the Draft studio's versioned blocks), so no earlier image is ever overwritten. Records live under
the project subtree and images under the project object prefix, so the existing recursive project
/ account delete removes them with no extra wiring.
"""

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class ThumbnailAspect(StrEnum):
    landscape = "16:9"
    portrait = "9:16"
    square = "1:1"


class ThumbnailStatus(StrEnum):
    queued = "queued"
    generating = "generating"
    ready = "ready"
    failed = "failed"


class ThumbnailCritique(BaseModel):
    """An honest read of a generated thumbnail, scored 1-5 on each axis."""

    #: Can the headline be read at phone size?
    legibility: int = Field(default=0, ge=0, le=5)
    #: Does the thumbnail promise what the video actually delivers? (anti-clickbait)
    promise: int = Field(default=0, ge=0, le=5)
    #: Does it fit the target platform's conventions?
    platformFit: int = Field(default=0, ge=0, le=5)
    summary: str = ""
    suggestions: list[str] = Field(default_factory=list)


class ThumbnailVersion(BaseModel):
    versionId: str
    #: 1-based, increasing.
    version: int
    storagePath: str | None = None
    mimeType: str = "image/png"
    width: int = 0
    height: int = 0
    sizeBytes: int = 0
    #: The model instruction that produced this version (the visual direction for v1,
    #: the creator's edit instruction afterwards).
    instruction: str = ""
    headline: str = ""
    rationale: str = ""
    #: Source-video offsets used as reference images for this version.
    referenceTimestampsMs: list[int] = Field(default_factory=list)
    critique: ThumbnailCritique | None = None
    model: str = ""
    costUsd: float = 0.0
    createdAt: datetime


class ThumbnailConcept(BaseModel):
    thumbnailId: str
    projectId: str
    status: ThumbnailStatus
    aspect: ThumbnailAspect = ThumbnailAspect.landscape
    #: The active headline/text baked into the image.
    headline: str = ""
    #: Why this concept works, citing the video's own evidence.
    rationale: str = ""
    #: Where the planner says the visual moment comes from.
    sourceTimestampMs: int | None = None
    referenceTimestampsMs: list[int] = Field(default_factory=list)
    activeVersionId: str | None = None
    versions: list[ThumbnailVersion] = Field(default_factory=list)
    #: True when this concept has been written to `project.thumbnailConcept`.
    isApplied: bool = False
    jobId: str | None = None
    error: dict[str, Any] | None = None
    #: Signed URL for the active version, minted on read for ready concepts.
    previewUrl: str | None = None
    createdAt: datetime
    updatedAt: datetime


class ThumbnailConceptList(BaseModel):
    items: list[ThumbnailConcept]


class GenerateThumbnailsRequest(BaseModel):
    #: How many distinct concepts to plan and render in one batch.
    count: int = Field(default=4, ge=1, le=6)
    aspect: ThumbnailAspect = ThumbnailAspect.landscape
    imageSize: str = "1K"
    #: Optional free-text direction for the planner (tone, must-include, must-avoid).
    brief: str = Field(default="", max_length=600)
    #: Use the project's real frames as references. Off means a prompt-only render.
    useRealFrames: bool = True
    #: Use the more expensive hero image model.
    useProModel: bool = False


class ReviseThumbnailRequest(BaseModel):
    #: A conversational edit, e.g. "make the headline bigger and warmer".
    instruction: str = Field(min_length=1, max_length=600)


class ThumbnailBatchAccepted(BaseModel):
    thumbnailIds: list[str]
    jobId: str
    status: str


class ThumbnailRevisionAccepted(BaseModel):
    thumbnailId: str
    jobId: str
    status: str


class ThumbnailSelectionRequest(BaseModel):
    """A set of concepts to act on in bulk (regenerate or download)."""

    thumbnailIds: list[str] = Field(min_length=1, max_length=24)
