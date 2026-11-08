from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from pathlib import Path

from pydantic import Field, field_validator

from blueframe.domain.common import DomainModel, require_aware


class LivePlatform(StrEnum):
    DOUYIN = "douyin"
    AUTHORIZED_URL = "authorized_url"


class RecordingSession(DomainModel):
    id: str
    project_id: str
    platform: LivePlatform
    display_name: str
    source_reference: str = Field(repr=False)
    authorization_confirmed_at: datetime
    intent_active: bool
    status: str
    process_id: int | None = None
    reconnect_count: int = Field(ge=0)
    error_summary: str | None = None
    created_at: datetime
    updated_at: datetime
    _aware = field_validator("authorization_confirmed_at", "created_at", "updated_at")(require_aware)


class RecordingSegment(DomainModel):
    id: str
    session_id: str
    sequence: int = Field(ge=0)
    path: Path
    status: str
    size_bytes: int = Field(ge=0)
    duration_ms: int = Field(ge=0)
    fingerprint: str | None = None
    created_at: datetime
    updated_at: datetime
    _aware = field_validator("created_at", "updated_at")(require_aware)
