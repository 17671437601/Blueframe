from __future__ import annotations

import importlib
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from pydantic import ValidationError


def _load_modules():
    return {
        name: importlib.import_module(f"blueframe.providers.{name}")
        for name in ("auth", "ai", "tts", "platform", "fakes")
    } | {"common": importlib.import_module("blueframe.domain.common")}


@pytest.mark.asyncio
async def test_fake_auth_provider_obeys_full_protocol() -> None:
    modules = _load_modules()
    auth = modules["auth"]
    fakes = modules["fakes"]
    now = datetime(2026, 11, 3, tzinfo=UTC)
    session = auth.AuthSession(
        access_token="access-value",
        refresh_token="refresh-value",
        expires_at=now + timedelta(hours=1),
    )
    profile = auth.UserProfile(user_id="user-1", display_name="测试用户")
    entitlements = auth.Entitlements(
        user_id="user-1",
        features={"local_asr", "remote_ai"},
        valid_from=now,
        valid_until=now + timedelta(days=30),
        concurrency_limit=2,
        daily_units=100,
        monthly_units=1_000,
        ai_tiers={"pro"},
        tts_tiers={"standard"},
    )
    provider = fakes.FakeAuthProvider(session, profile, entitlements)

    assert isinstance(provider, auth.AuthProvider)
    assert await provider.login({"username": "demo"}) == session
    assert await provider.refresh("refresh-value") == session
    assert await provider.current_user("access-value") == profile
    assert await provider.get_entitlements("access-value") == entitlements
    usage = auth.UsageEvent(feature="remote_ai", units=3, occurred_at=now)
    assert (await provider.report_usage("access-value", usage)).accepted is True
    assert await provider.logout("access-value") is None
    assert [call.operation for call in provider.calls] == [
        "login",
        "refresh",
        "current_user",
        "get_entitlements",
        "report_usage",
        "logout",
    ]


@pytest.mark.asyncio
async def test_fake_ai_provider_validates_output_schema() -> None:
    modules = _load_modules()
    ai = modules["ai"]
    common = modules["common"]
    provider = modules["fakes"].FakeAiProvider(
        output={"score": 88},
        provider="fixture",
        model="fixture-model",
        usage=common.ProviderUsage(input_units=10, output_units=2),
    )
    request = ai.AiRequest(
        operation="score_explosions",
        input={"episode_id": "episode-1"},
        output_schema={
            "type": "object",
            "required": ["score"],
            "properties": {"score": {"type": "integer", "minimum": 0}},
        },
    )

    result = await provider.execute(request)

    assert result.provider == "fixture"
    assert result.model == "fixture-model"
    assert result.output == {"score": 88}
    assert result.usage.input_units == 10


def test_models_reject_malformed_provider_data(tmp_path: Path) -> None:
    modules = _load_modules()
    auth = modules["auth"]
    ai = modules["ai"]
    common = modules["common"]
    now = datetime(2026, 11, 3, tzinfo=UTC)

    with pytest.raises(ValidationError):
        common.ProviderUsage(input_units=-1, output_units=0)
    with pytest.raises(ValidationError):
        ai.AiResult(
            provider="fixture",
            model="",
            usage=common.ProviderUsage(input_units=1, output_units=1),
            output={},
        )
    with pytest.raises(ValidationError):
        auth.Entitlements(
            user_id="user-1",
            features=set(),
            valid_from=now,
            valid_until=now - timedelta(seconds=1),
            concurrency_limit=1,
            daily_units=0,
            monthly_units=0,
            ai_tiers=set(),
            tts_tiers=set(),
        )
    with pytest.raises(ValidationError):
        auth.AuthSession(
            access_token="a",
            refresh_token="r",
            expires_at=datetime(2026, 11, 3),
        )


@pytest.mark.asyncio
async def test_tts_fake_rejects_artifact_outside_requested_root(tmp_path: Path) -> None:
    modules = _load_modules()
    tts = modules["tts"]
    provider = modules["fakes"].FakeTtsProvider(
        audio_path=tmp_path.parent / "escaped.wav"
    )
    request = tts.TtsRequest(
        text="测试旁白",
        voice="standard",
        output_root=tmp_path,
        filename="voice.wav",
    )

    with pytest.raises(ValueError, match="outside requested output root"):
        await provider.synthesize(request)
