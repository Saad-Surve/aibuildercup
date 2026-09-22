from datetime import datetime

from pydantic import BaseModel, Field


class TranscriptSegment(BaseModel):
    segmentId: str
    index: int
    startMs: int = Field(ge=0)
    endMs: int = Field(ge=0)
    text: str


class Transcript(BaseModel):
    transcriptId: str
    language: str
    durationMs: int = Field(ge=0)
    segments: list[TranscriptSegment] = Field(default_factory=list)


class TranscriptRecord(BaseModel):
    """Internal Firestore shape (superset of the public contract)."""

    transcriptId: str
    version: int
    status: str
    language: str
    sourceAssetId: str
    storagePath: str
    vttStoragePath: str
    durationMs: int
    wordCount: int
    segmentCount: int
    createdAt: datetime
    updatedAt: datetime
