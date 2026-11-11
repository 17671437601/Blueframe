from __future__ import annotations

from datetime import datetime
from pathlib import Path

from pydantic import Field, field_validator

from blueframe.domain.common import DomainModel, require_aware


class HighlightClipSpec(DomainModel):
    title: str = Field(min_length=1, max_length=200)
    reason: str = Field(min_length=1, max_length=1000)
    score: int = Field(ge=0, le=100)
    source_id: str = Field(min_length=1)
    start_ms: int = Field(ge=0)
    end_ms: int = Field(gt=0)

    @property
    def duration_ms(self) -> int:
        return self.end_ms - self.start_ms


class HighlightClip(DomainModel):
    id: str
    batch_id: str
    item_index: int = Field(ge=0)
    title: str
    reason: str
    score: int
    source_id: str
    start_ms: int
    end_ms: int
    status: str
    output_path: Path | None = None
    error_summary: str | None = None

    @property
    def duration_ms(self) -> int:
        return self.end_ms - self.start_ms


class HighlightBatch(DomainModel):
    id: str
    project_id: str
    analysis_version_id: str
    status: str
    target_count: int
    min_duration_ms: int
    max_duration_ms: int
    burn_subtitles: bool
    clips: tuple[HighlightClip, ...]
    created_at: datetime
    updated_at: datetime

    _aware = field_validator("created_at", "updated_at")(require_aware)
