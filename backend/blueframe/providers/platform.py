from __future__ import annotations

from typing import Protocol, runtime_checkable

from pydantic import AnyUrl, Field

from blueframe.domain.common import DomainModel


class LiveSource(DomainModel):
    platform: str = Field(min_length=1)
    stream_url: AnyUrl
    title: str | None = None


@runtime_checkable
class PlatformProvider(Protocol):
    async def resolve(self, page_url: str) -> LiveSource: ...
