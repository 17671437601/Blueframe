from __future__ import annotations

from datetime import datetime
from pathlib import Path

from pydantic import Field, field_validator, model_validator

from blueframe.domain.common import DomainModel, require_aware


class StorySegmentSpec(DomainModel):
    source_id: str = Field(min_length=1)
    start_ms: int = Field(ge=0)
    end_ms: int = Field(gt=0)

    @model_validator(mode="after")
    def valid_range(self) -> "StorySegmentSpec":
        if self.end_ms <= self.start_ms:
            raise ValueError("story segment end must be after start")
        return self

    @property
    def duration_ms(self) -> int:
        return self.end_ms - self.start_ms


class StoryPlanSpec(DomainModel):
    title: str = Field(min_length=1, max_length=200)
    target_duration_ms: int = Field(gt=0)
    segments: tuple[StorySegmentSpec, ...] = Field(min_length=1)

    @property
    def duration_ms(self) -> int:
        return sum(segment.duration_ms for segment in self.segments)


class StoryItem(DomainModel):
    id: str
    batch_id: str
    item_index: int = Field(ge=0)
    title: str
    target_duration_ms: int
    plan_id: str | None = None
    status: str
    output_path: Path | None = None
    error_summary: str | None = None


class StoryBatch(DomainModel):
    id: str
    project_id: str
    analysis_version_id: str
    status: str
    target_count: int
    min_duration_ms: int
    max_duration_ms: int
    burn_subtitles: bool
    items: tuple[StoryItem, ...]
    created_at: datetime
    updated_at: datetime

    _aware = field_validator("created_at", "updated_at")(require_aware)
