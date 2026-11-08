from __future__ import annotations

from enum import StrEnum

from pydantic import Field, model_validator

from blueframe.domain.common import DomainModel


class AsrStatus(StrEnum):
    COMPLETED = "completed"
    NO_AUDIO = "no_audio"


class EngineSegment(DomainModel):
    start_ms: int = Field(ge=0)
    end_ms: int = Field(gt=0)
    text: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_range(self) -> "EngineSegment":
        if self.end_ms <= self.start_ms:
            raise ValueError("segment end must be after start")
        return self


class AsrLine(DomainModel):
    index: int = Field(ge=0)
    start_ms: int = Field(ge=0)
    end_ms: int = Field(gt=0)
    text: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_range(self) -> "AsrLine":
        if self.end_ms <= self.start_ms:
            raise ValueError("line end must be after start")
        return self


class AsrDocument(DomainModel):
    id: str
    source_id: str
    cache_key: str
    model_version: str
    language: str
    duration_ms: int = Field(ge=0)
    status: AsrStatus
    lines: tuple[AsrLine, ...] = ()

    @model_validator(mode="after")
    def validate_timeline(self) -> "AsrDocument":
        previous_end = 0
        for expected_index, line in enumerate(self.lines):
            if line.index != expected_index:
                raise ValueError("ASR line indexes must be contiguous")
            if line.start_ms < previous_end:
                raise ValueError("ASR lines overlap")
            if line.end_ms > self.duration_ms:
                raise ValueError("ASR line exceeds media duration")
            previous_end = line.end_ms
        if self.status == AsrStatus.NO_AUDIO and self.lines:
            raise ValueError("no-audio document cannot contain lines")
        return self
