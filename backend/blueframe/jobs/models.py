from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import Field, field_validator

from blueframe.domain.common import DomainModel, require_aware


class JobStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    PAUSING = "pausing"
    PAUSED = "paused"
    CANCELLING = "cancelling"
    CANCELLED = "cancelled"
    COMPLETED = "completed"
    FAILED = "failed"
    INTERRUPTED = "interrupted"


class Job(DomainModel):
    id: str
    job_type: str
    payload: dict[str, Any]
    status: JobStatus
    priority: int = 0
    progress: float = Field(ge=0, le=100)
    stage: str | None = None
    attempts: int = Field(ge=0)
    lease_owner: str | None = None
    lease_expires_at: datetime | None = None
    checkpoint: dict[str, Any] | None = None
    idempotency_key: str
    error_code: str | None = None
    error_summary: str | None = None
    created_at: datetime
    updated_at: datetime

    _aware = field_validator("created_at", "updated_at")(require_aware)

    @field_validator("lease_expires_at")
    @classmethod
    def lease_datetime_is_aware(cls, value: datetime | None) -> datetime | None:
        return None if value is None else require_aware(value)
