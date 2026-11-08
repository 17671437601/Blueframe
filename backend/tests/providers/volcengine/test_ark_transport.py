from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from blueframe.providers.volcengine.config import ArkProviderConfig
from blueframe.providers.volcengine.transport import (
    ArkHttpResponse,
    ArkTransport,
    ArkTransportError,
)


class MemoryCredentials:
    def __init__(self, secret: str | None = "ark-secret") -> None:
        self.secret = secret

    def get(self, reference: str) -> str | None:
        assert reference == "memory:ark:key"
        return self.secret


def test_config_restricts_endpoint_and_redacts_credential_reference() -> None:
    config = ArkProviderConfig(
        credential_reference="memory:ark:key",
        model="endpoint-id",
    )
    assert config.responses_url == "https://ark.cn-beijing.volces.com/api/v3/responses"
    assert "memory:ark:key" not in repr(config)

    with pytest.raises(ValidationError):
        ArkProviderConfig(
            credential_reference="memory:ark:key",
            model="endpoint-id",
            base_url="https://attacker.example/api/v3",
        )


@pytest.mark.asyncio
async def test_transport_retries_rate_limit_without_leaking_secret() -> None:
    calls: list[tuple[str, dict[str, str], bytes, float]] = []
    sleeps: list[float] = []
    responses = iter(
        [
            ArkHttpResponse(429, {"Retry-After": "2"}, b'{"error":{"message":"slow"}}'),
            ArkHttpResponse(200, {}, b'{"id":"resp-ok"}'),
        ]
    )

    async def sender(url: str, headers: dict[str, str], body: bytes, timeout: float):
        calls.append((url, headers, body, timeout))
        return next(responses)

    async def sleep(delay: float) -> None:
        sleeps.append(delay)

    transport = ArkTransport(
        ArkProviderConfig(
            credential_reference="memory:ark:key",
            model="endpoint-id",
            timeout_seconds=7,
            max_attempts=2,
        ),
        MemoryCredentials(),
        sender=sender,
        sleep=sleep,
    )
    result = await transport.post_responses({"model": "endpoint-id", "input": "redacted"})

    assert result == {"id": "resp-ok"}
    assert sleeps == [2.0]
    assert len(calls) == 2
    assert calls[0][0].endswith("/api/v3/responses")
    assert calls[0][1]["Authorization"] == "Bearer ark-secret"
    assert calls[0][3] == 7


@pytest.mark.asyncio
async def test_transport_has_bounded_retry_and_safe_errors() -> None:
    async def sender(*_args):
        return ArkHttpResponse(500, {}, b'{"error":{"message":"ark-secret failed"}}')

    transport = ArkTransport(
        ArkProviderConfig(
            credential_reference="memory:ark:key",
            model="endpoint-id",
            max_attempts=2,
        ),
        MemoryCredentials(),
        sender=sender,
        sleep=lambda _delay: _async_none(),
    )
    with pytest.raises(ArkTransportError) as error:
        await transport.post_responses({"input": "private transcript"})
    assert error.value.status_code == 500
    assert "ark-secret" not in str(error.value)
    assert "private transcript" not in str(error.value)


async def _async_none() -> None:
    return None


@pytest.mark.asyncio
async def test_transport_rejects_missing_key_and_malformed_json() -> None:
    config = ArkProviderConfig(
        credential_reference="memory:ark:key",
        model="endpoint-id",
        max_attempts=1,
    )
    missing = ArkTransport(config, MemoryCredentials(None))
    with pytest.raises(ArkTransportError, match="not configured"):
        await missing.post_responses({})

    async def malformed(*_args):
        return ArkHttpResponse(200, {}, b"not-json")

    invalid = ArkTransport(config, MemoryCredentials(), sender=malformed)
    with pytest.raises(ArkTransportError, match="invalid JSON"):
        await invalid.post_responses({})
