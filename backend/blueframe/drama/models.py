from __future__ import annotations

from datetime import datetime

from pydantic import Field, field_validator, model_validator

from blueframe.domain.common import DomainModel, require_aware


class Character(DomainModel):
    name: str = Field(min_length=1, max_length=100)
    role: str = Field(min_length=1, max_length=100)
    description: str = Field(min_length=1, max_length=1000)


class Conflict(DomainModel):
    start_ms: int = Field(ge=0)
    end_ms: int = Field(gt=0)
    summary: str = Field(min_length=1, max_length=1000)

    @model_validator(mode="after")
    def valid_range(self) -> "Conflict":
        if self.end_ms <= self.start_ms:
            raise ValueError("conflict end must be after start")
        return self


class ExplosionCandidate(DomainModel):
    start_ms: int = Field(ge=0)
    end_ms: int = Field(gt=0)
    title: str = Field(min_length=1, max_length=200)
    reason: str = Field(min_length=1, max_length=1000)
    score: int = Field(ge=0, le=100)

    @model_validator(mode="after")
    def valid_range(self) -> "ExplosionCandidate":
        if self.end_ms <= self.start_ms:
            raise ValueError("explosion end must be after start")
        return self


class EdlCandidate(DomainModel):
    title: str = Field(min_length=1, max_length=200)
    rationale: str = Field(min_length=1, max_length=1000)
    segments: tuple[tuple[int, int], ...] = Field(min_length=1)

    @field_validator("segments")
    @classmethod
    def valid_segments(cls, segments: tuple[tuple[int, int], ...]):
        previous_end = -1
        for start_ms, end_ms in segments:
            if start_ms < 0 or end_ms <= start_ms:
                raise ValueError("EDL segment range is invalid")
            if start_ms < previous_end:
                raise ValueError("EDL segments must be ordered and non-overlapping")
            previous_end = end_ms
        return segments


class StoryAnalysis(DomainModel):
    episode_summary: str = Field(min_length=1, max_length=5000)
    characters: tuple[Character, ...] = ()
    conflicts: tuple[Conflict, ...] = ()
    explosions: tuple[ExplosionCandidate, ...] = ()
    edit_candidates: tuple[EdlCandidate, ...] = ()
    media_duration_ms: int = Field(gt=0)

    @model_validator(mode="after")
    def timeline_within_media(self) -> "StoryAnalysis":
        ranges = [
            (item.start_ms, item.end_ms)
            for item in (*self.conflicts, *self.explosions)
        ] + [segment for candidate in self.edit_candidates for segment in candidate.segments]
        if any(end_ms > self.media_duration_ms for _, end_ms in ranges):
            raise ValueError("analysis timeline exceeds media duration")
        return self


class StoryAnalysisVersion(DomainModel):
    id: str = Field(min_length=1)
    project_id: str = Field(min_length=1)
    version: int = Field(ge=1)
    prompt_version: str = Field(min_length=1)
    provider: str = Field(min_length=1)
    model: str = Field(min_length=1)
    analysis: StoryAnalysis
    accepted: bool = False
    created_at: datetime

    _aware = field_validator("created_at")(require_aware)
