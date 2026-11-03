from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


class DomainModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


def require_aware(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("datetime must be timezone-aware")
    return value


class ProviderUsage(DomainModel):
    input_units: int = Field(ge=0)
    output_units: int = Field(ge=0)


class ProviderCall(DomainModel):
    operation: str = Field(min_length=1)
    arguments: tuple[object, ...] = ()
