from __future__ import annotations

from pathlib import Path
from typing import Protocol, runtime_checkable

from pydantic import Field

from blueframe.domain.common import DomainModel, ProviderUsage


class TtsRequest(DomainModel):
    text: str = Field(min_length=1)
    voice: str = Field(min_length=1)
    output_root: Path
    filename: str = Field(min_length=1)


class TtsResult(DomainModel):
    provider: str = Field(min_length=1)
    audio_path: Path
    duration_ms: int = Field(ge=0)
    usage: ProviderUsage


@runtime_checkable
class TtsProvider(Protocol):
    async def synthesize(self, request: TtsRequest) -> TtsResult: ...
