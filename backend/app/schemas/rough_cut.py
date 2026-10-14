from typing import Literal

from pydantic import BaseModel, Field


class RoughCutRequest(BaseModel):
    findingIds: list[str] | None = Field(default=None, max_length=200)
    labels: dict[str, Literal["cut", "note"]] = Field(default_factory=dict)
    insertIds: list[str] = Field(default_factory=list, max_length=8)


class KeptSegment(BaseModel):
    sourceStartMs: int
    sourceEndMs: int
    outputStartMs: int


class RemovedSpan(BaseModel):
    startMs: int
    endMs: int
    findingId: str
    findingIds: list[str] = Field(default_factory=list)


class RoughCutMetadata(BaseModel):
    sourceAssetId: str
    analysisRunId: str
    findingIds: list[str]
    keptSegments: list[KeptSegment]
    removedSpans: list[RemovedSpan]
    durationMsBefore: int
    durationMsAfter: int
    insertIds: list[str] = Field(default_factory=list)


class InsertPlacement(BaseModel):
    insertStartMs: int
    outputStartMs: int
    outputEndMs: int


class PlannedInsert(BaseModel):
    insertId: str
    headline: str
    placements: list[InsertPlacement] = Field(default_factory=list)
    skippedReason: str | None = None


class PlannedFinding(BaseModel):
    findingId: str
    startMs: int
    endMs: int
    dimension: str
    action: str
    label: Literal["cut", "note"]
    labelReason: str
    skippedReason: str | None = None


class RoughCutPlan(RoughCutMetadata):
    findings: list[PlannedFinding]
    inserts: list[PlannedInsert] = Field(default_factory=list)


class RoughCutAccepted(BaseModel):
    jobId: str
    assetId: str
    status: str
    plan: RoughCutPlan
