from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field

from app.schemas.draft import DraftBrief, DraftFormat, DraftSummary


class ProjectKind(StrEnum):
    video = "video"
    draft = "draft"


class ProjectStatus(StrEnum):
    draft = "draft"
    uploading = "uploading"
    processing = "processing"
    ready = "ready"
    partial_failure = "partial_failure"
    failed = "failed"
    archived = "archived"


class CreateProject(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str = ""
    #: Packaging context for the reviewers: what the thumbnail promises.
    thumbnailConcept: str = ""
    primaryLanguage: str = "en"
    targetLanguages: list[str] = Field(default_factory=list)
    targetPlatforms: list[str] = Field(default_factory=list)
    #: `video` runs the upload -> transcript -> review pipeline; `draft` opens
    #: the versioned writing studio instead.
    kind: ProjectKind = ProjectKind.video
    draftFormat: DraftFormat = DraftFormat.written
    #: Seed brief for a draft project, captured in the creation dialog.
    draftBrief: DraftBrief | None = None
    isDemo: bool = False
    demoProfileId: str | None = None


class UpdateProject(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = None
    thumbnailConcept: str | None = None


class ProjectProgress(BaseModel):
    stage: str | None = None
    percent: int = 0
    message: str | None = None


class Project(BaseModel):
    projectId: str
    name: str
    description: str
    thumbnailConcept: str = ""
    primaryLanguage: str
    targetLanguages: list[str]
    targetPlatforms: list[str]
    kind: ProjectKind = ProjectKind.video
    draftFormat: DraftFormat = DraftFormat.written
    draftSummary: DraftSummary | None = None
    isDemo: bool
    demoProfileId: str | None
    status: ProjectStatus
    progress: ProjectProgress | None = None
    #: Active source-video pointer and revision summary (see `Revision`).
    sourceAssetId: str | None = None
    sourceRevision: int | None = None
    revisionCount: int = 0
    createdAt: datetime
    updatedAt: datetime


class ProjectList(BaseModel):
    items: list[Project]
    nextPageToken: str | None = None
