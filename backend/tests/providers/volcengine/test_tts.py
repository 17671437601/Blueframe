from __future__ import annotations

import base64
from pathlib import Path

import pytest

from blueframe.auth.credential_store import InMemoryCredentialStore
from blueframe.providers.tts import TtsRequest, TtsResult
from blueframe.providers.volcengine.tts import (
    CachedTtsProvider,
    TtsCache,
    VolcengineTtsConfig,
    VolcengineTtsProvider,
)


@pytest.mark.asyncio
async def test_tts_uses_official_headers_and_assembles_base64_chunks(tmp_path: Path) -> None:
    credentials = InMemoryCredentialStore()
    reference = credentials.put("tts", "speech-secret")
    calls = []

    async def sender(url, headers, payload, timeout):
        calls.append((url, headers, payload, timeout))
        return [
            {"code": 0, "message": "OK", "data": base64.b64encode(b"audio-").decode()},
            {"code": 0, "message": "OK", "data": base64.b64encode(b"bytes").decode(), "usage": {"text_words": 4}},
        ]

    provider = VolcengineTtsProvider(
        VolcengineTtsConfig(credential_reference=reference), credentials,
        sender=sender, duration_probe=lambda _path: 1234,
    )
    result = await provider.synthesize(TtsRequest(
        text="你好 AI。", voice="zh_female_vv_uranus_bigtts",
        output_root=tmp_path, filename="voice.mp3", speech_rate=10,
    ))

    assert result.audio_path.read_bytes() == b"audio-bytes"
    assert (result.duration_ms, result.usage.input_units) == (1234, 4)
    assert calls[0][0] == "https://openspeech.bytedance.com/api/v3/tts/unidirectional"
    assert calls[0][1]["X-Api-Key"] == "speech-secret"
    assert calls[0][1]["X-Api-Resource-Id"] == "seed-tts-2.0"
    assert calls[0][2]["req_params"]["audio_params"]["speech_rate"] == 10


class CountingProvider:
    def __init__(self): self.calls = 0
    async def synthesize(self, request):
        self.calls += 1
        path = request.output_root / request.filename
        path.parent.mkdir(parents=True, exist_ok=True); path.write_bytes(b"cached-audio")
        return TtsResult(provider="fixture", audio_path=path, duration_ms=900, usage={"input_units": 3, "output_units": 1})


@pytest.mark.asyncio
async def test_tts_cache_normalizes_text_and_keys_voice_rate_model_version(tmp_path: Path) -> None:
    upstream = CountingProvider()
    cached = CachedTtsProvider(upstream, TtsCache(tmp_path / "cache"), model="seed-tts-2.0", provider_version="v3")
    first = await cached.synthesize(TtsRequest(text="你好，  世界", voice="voice-a", output_root=tmp_path / "out", filename="one.mp3"))
    second = await cached.synthesize(TtsRequest(text="你好， 世界", voice="voice-a", output_root=tmp_path / "other", filename="two.mp3"))
    third = await cached.synthesize(TtsRequest(text="你好， 世界", voice="voice-a", output_root=tmp_path / "out", filename="fast.mp3", speech_rate=20))

    assert first.audio_path.read_bytes() == second.audio_path.read_bytes() == b"cached-audio"
    assert upstream.calls == 2
    assert third.duration_ms == 900
