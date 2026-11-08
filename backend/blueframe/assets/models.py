from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from pathlib import Path

from pydantic import Field, field_validator

from blueframe.domain.common import DomainModel, require_aware


class AssetType(StrEnum):
    VIDEO = "video"
    AUDIO = "audio"
    IMAGE = "image"
    FONT = "font"


class StorageOwnership(StrEnum):
    LINKED = "linked"
    MANAGED = "managed"


class AssetDraft(DomainModel):
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    asset_type: AssetType
    path: Path
    origin: str = Field(min_length=1, max_length=500)
    license_name: str = Field(min_length=1, max_length=500)
    ownership: StorageOwnership
    metadata: dict = Field(default_factory=dict)


class Asset(AssetDraft):
    id: str = Field(min_length=1)
    available: bool
    created_at: datetime
    updated_at: datetime

    _aware = field_validator("created_at", "updated_at")(require_aware)
