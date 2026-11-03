from __future__ import annotations

from pathlib import Path
from typing import Any

from jsonschema import validate

from blueframe.domain.common import ProviderCall, ProviderUsage
from blueframe.providers.ai import AiRequest, AiResult
from blueframe.providers.auth import Ack, AuthSession, Entitlements, UsageEvent, UserProfile
from blueframe.providers.tts import TtsRequest, TtsResult


class FakeAuthProvider:
    def __init__(self, session: AuthSession, profile: UserProfile, entitlements: Entitlements):
        self.session = session
        self.profile = profile
        self.entitlements = entitlements
        self.calls: list[ProviderCall] = []

    async def login(self, credentials: dict[str, Any]) -> AuthSession:
        self.calls.append(ProviderCall(operation="login", arguments=(credentials,)))
        return self.session

    async def refresh(self, refresh_token: str) -> AuthSession:
        self.calls.append(ProviderCall(operation="refresh", arguments=(refresh_token,)))
        return self.session

    async def current_user(self, access_token: str) -> UserProfile:
        self.calls.append(ProviderCall(operation="current_user", arguments=(access_token,)))
        return self.profile

    async def get_entitlements(self, access_token: str) -> Entitlements:
        self.calls.append(ProviderCall(operation="get_entitlements", arguments=(access_token,)))
        return self.entitlements

    async def report_usage(self, access_token: str, usage_event: UsageEvent) -> Ack:
        self.calls.append(ProviderCall(operation="report_usage", arguments=(access_token, usage_event)))
        return Ack(accepted=True)

    async def logout(self, access_token: str) -> None:
        self.calls.append(ProviderCall(operation="logout", arguments=(access_token,)))


class FakeAiProvider:
    def __init__(self, *, output: dict[str, Any], provider: str, model: str, usage: ProviderUsage):
        self.output, self.provider, self.model, self.usage = output, provider, model, usage
        self.calls: list[AiRequest] = []

    async def execute(self, request: AiRequest) -> AiResult:
        validate(instance=self.output, schema=request.output_schema)
        self.calls.append(request)
        return AiResult(provider=self.provider, model=self.model, usage=self.usage, output=self.output)


class FakeTtsProvider:
    def __init__(self, audio_path: Path):
        self.audio_path = audio_path

    async def synthesize(self, request: TtsRequest) -> TtsResult:
        root = request.output_root.resolve()
        artifact = self.audio_path.resolve()
        if not artifact.is_relative_to(root):
            raise ValueError("audio artifact is outside requested output root")
        return TtsResult(
            provider="fixture",
            audio_path=artifact,
            duration_ms=1_000,
            usage=ProviderUsage(input_units=len(request.text), output_units=1),
        )
