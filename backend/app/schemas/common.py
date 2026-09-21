from typing import Any

from pydantic import BaseModel, Field


class ErrorDetail(BaseModel):
    code: str
    message: str
    requestId: str | None = None
    details: dict[str, Any] = Field(default_factory=dict)


class ErrorResponse(BaseModel):
    error: ErrorDetail


class AcceptedJob(BaseModel):
    jobId: str
    status: str
