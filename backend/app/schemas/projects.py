from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field


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
    primaryLanguage: str = "en"
    targetLanguages: list[str] = Field(default_factory=list)
    targetPlatforms: list[str] = Field(default_factory=list)
    isDemo: bool = False
    demoProfileId: str | None = None


class UpdateProject(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = None


class Project(BaseModel):
    projectId: str
    name: str
    description: str
    primaryLanguage: str
    targetLanguages: list[str]
    targetPlatforms: list[str]
    isDemo: bool
    demoProfileId: str | None
    status: ProjectStatus
    createdAt: datetime
    updatedAt: datetime


class ProjectList(BaseModel):
    items: list[Project]
    nextPageToken: str | None = None
