from datetime import datetime

from pydantic import BaseModel, Field


class TranscriptSegment(BaseModel):
    segmentId: str
    index: int
    startMs: int = Field(ge=0)
    endMs: int = Field(ge=0)
    text: str
    # Speaker index from STT diarization. None when diarization is off or undetected.
    speaker: int | None = None


class Transcript(BaseModel):
    transcriptId: str
    language: str
    durationMs: int = Field(ge=0)
    segments: list[TranscriptSegment] = Field(default_factory=list)
    # Speaker index -> short role/name inferred during transcript cleanup (for example
    # {"0": "Host", "1": "Guest"}). Empty when the voices could not be named.
    speakerLabels: dict[str, str] = Field(default_factory=dict)


class TranscriptSegmentUpdate(BaseModel):
    """One edited segment submitted by the transcript editor."""

    segmentId: str
    index: int = Field(ge=0)
    startMs: int = Field(ge=0)
    endMs: int = Field(ge=0)
    text: str
    speaker: int | None = None


class TranscriptUpdate(BaseModel):
    """Replace the active transcript with edited segments (saved as a new version)."""

    language: str | None = None
    segments: list[TranscriptSegmentUpdate] = Field(default_factory=list)


class TranscriptRecord(BaseModel):
    """Internal Firestore shape (superset of the public contract)."""

    transcriptId: str
    version: int
    status: str
    language: str
    sourceAssetId: str
    storagePath: str
    vttStoragePath: str
    srtStoragePath: str
    durationMs: int
    wordCount: int
    segmentCount: int
    createdAt: datetime
    updatedAt: datetime


class TranscriptVersion(BaseModel):
    """One saved transcript generation, for the version picker."""

    transcriptId: str
    version: int
    language: str
    durationMs: int = Field(ge=0)
    wordCount: int = 0
    createdAt: datetime | None = None


class TranscriptVersionList(BaseModel):
    items: list[TranscriptVersion] = Field(default_factory=list)
