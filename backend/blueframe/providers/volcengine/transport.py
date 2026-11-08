from __future__ import annotations

import asyncio
import json
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from blueframe.auth.credential_store import CredentialStore
from blueframe.providers.volcengine.config import ArkProviderConfig


@dataclass(frozen=True)
class ArkHttpResponse:
    status_code: int
    headers: Mapping[str, str]
    body: bytes


class ArkTransportError(RuntimeError):
    def __init__(self, message: str, *, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


Sender = Callable[[str, dict[str, str], bytes, float], Awaitable[ArkHttpResponse]]
Sleeper = Callable[[float], Awaitable[None]]


class ArkTransport:
    def __init__(
        self,
        config: ArkProviderConfig,
        credential_store: CredentialStore,
        *,
        sender: Sender | None = None,
        sleep: Sleeper = asyncio.sleep,
    ) -> None:
        self.config = config
        self.credential_store = credential_store
        self.sender = sender or _send
        self.sleep = sleep

    async def post_responses(self, payload: dict) -> dict:
        api_key = self.credential_store.get(self.config.credential_reference)
        if not api_key:
            raise ArkTransportError("Volcengine API key is not configured")
        body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        response: ArkHttpResponse | None = None
        for attempt in range(self.config.max_attempts):
            try:
                response = await self.sender(
                    self.config.responses_url,
                    headers,
                    body,
                    self.config.timeout_seconds,
                )
            except (TimeoutError, OSError, URLError) as error:
                if attempt + 1 >= self.config.max_attempts:
                    raise ArkTransportError("Volcengine request failed") from error
                await self.sleep(_backoff(attempt))
                continue

            if response.status_code < 400:
                return _decode_json(response.body)
            if response.status_code not in {408, 409, 429, 500, 502, 503, 504}:
                raise ArkTransportError(
                    "Volcengine rejected the request", status_code=response.status_code
                )
            if attempt + 1 >= self.config.max_attempts:
                break
            await self.sleep(_retry_delay(response.headers, attempt))

        raise ArkTransportError(
            "Volcengine request failed after retry",
            status_code=response.status_code if response else None,
        )


def _decode_json(body: bytes) -> dict:
    try:
        value = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ArkTransportError("Volcengine returned invalid JSON") from error
    if not isinstance(value, dict):
        raise ArkTransportError("Volcengine returned invalid JSON")
    return value


def _retry_delay(headers: Mapping[str, str], attempt: int) -> float:
    value = next(
        (header_value for name, header_value in headers.items() if name.lower() == "retry-after"),
        None,
    )
    if value is not None:
        try:
            return min(max(float(value), 0), 30)
        except ValueError:
            pass
    return _backoff(attempt)


def _backoff(attempt: int) -> float:
    return min(0.5 * (2**attempt), 8.0)


async def _send(
    url: str, headers: dict[str, str], body: bytes, timeout: float
) -> ArkHttpResponse:
    return await asyncio.to_thread(_send_sync, url, headers, body, timeout)


def _send_sync(
    url: str, headers: dict[str, str], body: bytes, timeout: float
) -> ArkHttpResponse:
    request = Request(url, headers=headers, data=body, method="POST")
    try:
        with urlopen(request, timeout=timeout) as response:
            return ArkHttpResponse(response.status, dict(response.headers), response.read())
    except HTTPError as error:
        return ArkHttpResponse(error.code, dict(error.headers), error.read())
