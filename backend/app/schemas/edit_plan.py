from enum import IntEnum
from typing import Literal

from pydantic import BaseModel, Field


class ExportFrameRate(IntEnum):
    fps24 = 24
    fps25 = 25
    fps30 = 30
    fps60 = 60


class KeptSegment(BaseModel):
    sourceStartMs: int
    sourceEndMs: int
    outputStartMs: int


class RemovedSpan(BaseModel):
    startMs: int
    endMs: int
    findingId: str
    findingIds: list[str] = Field(default_factory=list)


class EditPlanMetadata(BaseModel):
    sourceAssetId: str
    analysisRunId: str
    findingIds: list[str]
    keptSegments: list[KeptSegment]
    removedSpans: list[RemovedSpan]
    durationMsBefore: int
    durationMsAfter: int


class PlannedFinding(BaseModel):
    findingId: str
    startMs: int
    endMs: int
    dimension: str
    action: str
    label: Literal["cut", "note"]
    labelReason: str
    skippedReason: str | None = None


class EditPlan(EditPlanMetadata):
    findings: list[PlannedFinding]
