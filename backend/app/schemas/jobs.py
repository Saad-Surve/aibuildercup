from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel


class JobType(StrEnum):
    upload = "upload"
    transcribe = "transcribe"
    analyze = "analyze"
    sync_social = "sync_social"
    sentiment = "sentiment"
    clip = "clip"
    thumbnail = "thumbnail"
    localize = "localize"
    dub = "dub"
    text_content = "text_content"
    veo = "veo"
    export = "export"
    caption_render = "caption_render"
    rough_cut = "rough_cut"  # Read-only compatibility for historical job documents.
    publish = "publish"


class JobStatus(StrEnum):
    queued = "queued"
    running = "running"
    succeeded = "succeeded"
    failed = "failed"
    cancelled = "cancelled"


class JobProgress(BaseModel):
    percent: int = 0
    step: str | None = None
    message: str | None = None


class Job(BaseModel):
    jobId: str
    type: JobType
    status: JobStatus
    progress: JobProgress
    error: dict[str, Any] | None = None
    createdAt: datetime
    updatedAt: datetime
