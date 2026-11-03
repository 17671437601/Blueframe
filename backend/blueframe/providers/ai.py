from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from pydantic import Field

from blueframe.domain.common import DomainModel, ProviderUsage


class AiRequest(DomainModel):
    operation: str = Field(min_length=1)
    input: dict[str, Any]
    output_schema: dict[str, Any]
    model_hint: str | None = None


class AiResult(DomainModel):
    provider: str = Field(min_length=1)
    model: str = Field(min_length=1)
    usage: ProviderUsage
    output: dict[str, Any]


@runtime_checkable
class AiProvider(Protocol):
    async def execute(self, request: AiRequest) -> AiResult: ...
