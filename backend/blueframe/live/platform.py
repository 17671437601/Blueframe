from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Protocol, runtime_checkable
from urllib.parse import urlparse

from pydantic import Field

from blueframe.auth.credential_store import CredentialStore
from blueframe.domain.common import DomainModel


class StreamSource(DomainModel):
    platform: str = Field(min_length=1)
    source_reference: str = Field(min_length=1, repr=False)
    display_name: str = Field(min_length=1)


class ResolvedStream(DomainModel):
    platform: str
    title: str
    playback_url: str = Field(repr=False)
    expires_at: datetime | None = None


@runtime_checkable
class LivePlatformAdapter(Protocol):
    async def resolve(self, source: StreamSource) -> ResolvedStream: ...


class AuthorizedUrlAdapter:
    """Resolves only a URL explicitly supplied by an authorized user."""
    def __init__(self, credentials: CredentialStore, *, clock=lambda: datetime.now(UTC), maximum_age=timedelta(hours=6)) -> None:
        self.credentials, self.clock, self.maximum_age = credentials, clock, maximum_age

    async def resolve(self, source: StreamSource) -> ResolvedStream:
        url = self.credentials.get(source.source_reference)
        if not url: raise RuntimeError("authorized live URL is unavailable")
        parsed = urlparse(url)
        if parsed.scheme not in {"https", "rtmp", "rtmps", "srt"} or not parsed.hostname:
            raise ValueError("unsupported authorized live URL")
        return ResolvedStream(
            platform=source.platform, title=source.display_name, playback_url=url,
            expires_at=self.clock() + self.maximum_age,
        )


class DouyinAuthorizedAdapter(AuthorizedUrlAdapter):
    """Douyin-labelled adapter; intentionally does not scrape pages or derive private URLs."""
    async def resolve(self, source: StreamSource) -> ResolvedStream:
        if source.platform != "douyin": raise ValueError("Douyin adapter received a different platform")
        return await super().resolve(source)
