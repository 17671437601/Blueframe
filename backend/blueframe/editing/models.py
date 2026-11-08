from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum

from pydantic import Field, computed_field, model_validator

from blueframe.domain.common import DomainModel


class PlanKind(StrEnum):
    HIGHLIGHT = "highlight"
    REMIX = "remix"
    COMMENTARY = "commentary"


class EditSegment(DomainModel):
    source_id: str = Field(min_length=1)
    source_start_ms: int = Field(ge=0)
    source_end_ms: int = Field(gt=0)
    source_duration_ms: int = Field(gt=0)

    @model_validator(mode="after")
    def valid_source_range(self) -> "EditSegment":
        if self.source_end_ms <= self.source_start_ms:
            raise ValueError("segment end must be after start")
        if self.source_end_ms > self.source_duration_ms:
            raise ValueError("segment exceeds source duration")
        return self

    @computed_field
    @property
    def duration_ms(self) -> int:
        return self.source_end_ms - self.source_start_ms


class EditPlanDraft(DomainModel):
    title: str = Field(min_length=1, max_length=200)
    kind: PlanKind
    target_duration_ms: int = Field(gt=0)
    segments: tuple[EditSegment, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def valid_timeline(self) -> "EditPlanDraft":
        if any(segment.duration_ms < 500 for segment in self.segments):
            raise ValueError("edit segments must be at least 500ms")
        previous_by_source: dict[str, int] = {}
        for segment in self.segments:
            previous_end = previous_by_source.get(segment.source_id, -1)
            if segment.source_start_ms < previous_end:
                raise ValueError("segments from the same source overlap or are out of order")
            previous_by_source[segment.source_id] = segment.source_end_ms
        return self

    @computed_field
    @property
    def duration_ms(self) -> int:
        return sum(segment.duration_ms for segment in self.segments)


class EditPlan(EditPlanDraft):
    id: str = Field(min_length=1)
    project_id: str = Field(min_length=1)
    version: int = Field(ge=1)
    idempotency_key: str = ""
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
