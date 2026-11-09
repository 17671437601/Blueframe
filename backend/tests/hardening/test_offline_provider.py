from __future__ import annotations

import pytest

from blueframe.providers.volcengine.config import ArkProviderConfig
from blueframe.providers.volcengine.transport import ArkTransport, ArkTransportError


class MemoryCredentials:
    def get(self, reference: str) -> str | None:
        return "ark-secret"


def config(**overrides) -> ArkProviderConfig:
    return ArkProviderConfig(
        credential_reference="memory:ark:key", model="endpoint-id", **overrides
    )


@pytest.mark.asyncio
async def test_offline_network_failures_retry_with_backoff_then_fail_safely() -> None:
    attempts: list[int] = []
    sleeps: list[float] = []

    async def sender(*_args):
        attempts.append(1)
        raise OSError("network is unreachable")

    async def sleep(delay: float) -> None:
        sleeps.append(delay)

    transport = ArkTransport(
        config(max_attempts=3), MemoryCredentials(), sender=sender, sleep=sleep,
    )

    with pytest.raises(ArkTransportError, match="failed") as error:
        await transport.post_responses({"input": "private transcript"})

    assert len(attempts) == 3
    assert sleeps == [0.5, 1.0]
    assert "ark-secret" not in str(error.value)
    assert "private transcript" not in str(error.value)


@pytest.mark.asyncio
async def test_timeout_is_retried_then_reported_without_request_body() -> None:
    attempts: list[int] = []

    async def sender(*_args):
        attempts.append(1)
        raise TimeoutError("read timed out")

    async def sleep(_delay: float) -> None:
        return None

    transport = ArkTransport(
        config(max_attempts=2), MemoryCredentials(), sender=sender, sleep=sleep,
    )

    with pytest.raises(ArkTransportError) as error:
        await transport.post_responses({"input": "private transcript"})

    assert len(attempts) == 2
    assert error.value.status_code is None
    assert "private transcript" not in str(error.value)
