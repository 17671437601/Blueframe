from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from pathlib import Path, PurePosixPath
from typing import Any

from pydantic import Field, field_validator

from blueframe.domain.common import DomainModel, require_aware


class ProjectType(StrEnum):
    DRAMA = "drama"
    MOVIE = "movie"
    VARIANTS = "variants"
    LIVE = "live"


class ProjectStatus(StrEnum):
    DRAFT = "draft"
    READY = "ready"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    ARCHIVED = "archived"


class ProjectConfigSnapshot(DomainModel):
    version: int = Field(ge=1)
    values: dict[str, Any]


class Project(DomainModel):
    id: str
    name: str = Field(min_length=1, max_length=300)
    project_type: ProjectType
    status: ProjectStatus
    root_path: Path
    output_relative_path: str
    config: ProjectConfigSnapshot
    idempotency_key: str
    created_at: datetime
    updated_at: datetime

    _aware = field_validator("created_at", "updated_at")(require_aware)


class SourceRegistration(DomainModel):
    relative_path: str
    size_bytes: int = Field(ge=0)
    modified_ns: int = Field(ge=0)
    content_fingerprint: str = Field(min_length=1, max_length=128)

    @field_validator("relative_path")
    @classmethod
    def safe_relative_path(cls, value: str) -> str:
        normalized = value.replace("\\", "/")
        candidate = PurePosixPath(normalized)
        if candidate.is_absolute() or ".." in candidate.parts or not normalized.strip():
            raise ValueError("source path must remain relative to the project root")
        return candidate.as_posix()


class ProjectSource(DomainModel):
    id: str
    project_id: str
    relative_path: str
    order_index: int = Field(ge=0)
    size_bytes: int = Field(ge=0)
    modified_ns: int = Field(ge=0)
    content_fingerprint: str
    media_info: dict[str, Any] | None = None
    created_at: datetime
    updated_at: datetime

    _aware = field_validator("created_at", "updated_at")(require_aware)
