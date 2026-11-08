import asyncio
from datetime import UTC, datetime, timedelta

from blueframe.auth.credential_store import InMemoryCredentialStore
from blueframe.live.platform import AuthorizedUrlAdapter, StreamSource


def test_authorized_url_adapter_reads_secret_outside_sqlite_and_returns_expiry() -> None:
    credentials = InMemoryCredentialStore(); reference = credentials.put("live", "https://example.test/live.m3u8?token=secret")
    adapter = AuthorizedUrlAdapter(credentials, clock=lambda: datetime(2026, 1, 1, tzinfo=UTC))
    resolved = asyncio.run(adapter.resolve(StreamSource(platform="douyin", source_reference=reference, display_name="测试直播")))
    assert resolved.playback_url.startswith("https://")
    assert resolved.expires_at == datetime(2026, 1, 1, tzinfo=UTC) + timedelta(hours=6)
