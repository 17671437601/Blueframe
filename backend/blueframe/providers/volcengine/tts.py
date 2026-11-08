from __future__ import annotations

import asyncio
import base64
import hashlib
import json
import os
import re
import shutil
import unicodedata
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Literal
from urllib.request import Request, urlopen
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

from blueframe.auth.credential_store import CredentialStore
from blueframe.domain.common import ProviderUsage
from blueframe.providers.tts import TtsProvider, TtsRequest, TtsResult


class VolcengineTtsConfig(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    credential_reference: str = Field(min_length=1, repr=False)
    endpoint: Literal["https://openspeech.bytedance.com/api/v3/tts/unidirectional"] = "https://openspeech.bytedance.com/api/v3/tts/unidirectional"
    resource_id: str = "seed-tts-2.0"
    timeout_seconds: float = Field(default=90, ge=1, le=300)
    sample_rate: int = 24000
    default_voice: str = "zh_female_vv_uranus_bigtts"


class VolcengineTtsConfigStatus(BaseModel):
    model_config = ConfigDict(frozen=True)
    configured: bool
    default_voice: str | None


class VolcengineTtsConfigService:
    def __init__(self, path: Path, credentials: CredentialStore) -> None:
        self.path, self.credentials = path, credentials

    def load(self) -> VolcengineTtsConfig | None:
        return None if not self.path.exists() else VolcengineTtsConfig.model_validate_json(self.path.read_text("utf-8"))

    def status(self) -> VolcengineTtsConfigStatus:
        config = self.load()
        return VolcengineTtsConfigStatus(
            configured=config is not None and self.credentials.get(config.credential_reference) is not None,
            default_voice=None if config is None else config.default_voice,
        )

    def configure(self, *, default_voice: str, api_key: str | None = None) -> VolcengineTtsConfigStatus:
        current = self.load()
        if api_key:
            reference = self.credentials.put("provider:volcengine-tts", api_key)
            if current is not None and current.credential_reference != reference:
                self.credentials.delete(current.credential_reference)
        elif current is not None:
            reference = current.credential_reference
        else:
            raise ValueError("API key is required for initial TTS configuration")
        config = VolcengineTtsConfig(credential_reference=reference, default_voice=default_voice)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(".tmp")
        temporary.write_text(config.model_dump_json(indent=2), encoding="utf-8")
        os.replace(temporary, self.path)
        return self.status()


TtsSender = Callable[[str, dict[str, str], dict, float], Awaitable[list[dict]]]


class VolcengineTtsProvider:
    def __init__(
        self, config: VolcengineTtsConfig, credentials: CredentialStore, *,
        sender: TtsSender | None = None,
        duration_probe: Callable[[Path], int],
    ) -> None:
        self.config, self.credentials = config, credentials
        self.sender = sender or _send
        self.duration_probe = duration_probe

    async def synthesize(self, request: TtsRequest) -> TtsResult:
        api_key = self.credentials.get(self.config.credential_reference)
        if not api_key:
            raise RuntimeError("Volcengine TTS API key is not configured")
        request_id = str(uuid4())
        frames = await self.sender(
            self.config.endpoint,
            {
                "X-Api-Key": api_key,
                "X-Api-Resource-Id": self.config.resource_id,
                "X-Api-Request-Id": request_id,
                "X-Control-Require-Usage-Tokens-Return": "*",
                "Content-Type": "application/json",
            },
            {"req_params": {
                "text": request.text,
                "speaker": request.voice,
                "audio_params": {
                    "format": "mp3", "sample_rate": self.config.sample_rate,
                    "speech_rate": request.speech_rate,
                },
            }},
            self.config.timeout_seconds,
        )
        audio = bytearray(); usage = 0
        for frame in frames:
            if int(frame.get("code", -1)) != 0:
                raise RuntimeError("Volcengine TTS synthesis failed")
            if frame.get("data"):
                try:
                    audio.extend(base64.b64decode(frame["data"], validate=True))
                except (ValueError, TypeError) as error:
                    raise RuntimeError("Volcengine TTS returned invalid audio") from error
            usage = max(usage, int((frame.get("usage") or {}).get("text_words") or 0))
        if not audio:
            raise RuntimeError("Volcengine TTS returned no audio")
        root = request.output_root.resolve(); root.mkdir(parents=True, exist_ok=True)
        output = (root / request.filename).resolve()
        if not output.is_relative_to(root):
            raise ValueError("TTS output escapes requested root")
        temporary = output.with_suffix(output.suffix + ".tmp")
        temporary.write_bytes(audio); os.replace(temporary, output)
        return TtsResult(
            provider="volcengine-tts", audio_path=output,
            duration_ms=self.duration_probe(output),
            usage=ProviderUsage(input_units=usage or len(request.text), output_units=len(audio)),
        )


async def _send(url: str, headers: dict[str, str], payload: dict, timeout: float) -> list[dict]:
    return await asyncio.to_thread(_send_sync, url, headers, payload, timeout)


def _send_sync(url: str, headers: dict[str, str], payload: dict, timeout: float) -> list[dict]:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = Request(url, data=body, headers=headers, method="POST")
    frames = []
    with urlopen(request, timeout=timeout) as response:
        for line in response:
            if line.strip():
                frames.append(json.loads(line.decode("utf-8")))
    return frames


class TtsCache:
    def __init__(self, root: Path) -> None:
        self.root = root

    def key(self, request: TtsRequest, *, model: str, provider_version: str) -> str:
        normalized = unicodedata.normalize("NFKC", request.text)
        normalized = re.sub(r"\s+", " ", normalized).strip()
        material = json.dumps({
            "text": normalized, "voice": request.voice,
            "speech_rate": request.speech_rate, "model": model,
            "provider_version": provider_version,
        }, ensure_ascii=False, sort_keys=True)
        return hashlib.sha256(material.encode("utf-8")).hexdigest()

    def get(self, key: str) -> tuple[Path, dict] | None:
        audio = self.root / f"{key}.mp3"; manifest = self.root / f"{key}.json"
        if not audio.is_file() or not manifest.is_file(): return None
        return audio, json.loads(manifest.read_text("utf-8"))

    def put(self, key: str, source: Path, result: TtsResult) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        audio = self.root / f"{key}.mp3"; temporary = audio.with_suffix(".tmp")
        shutil.copyfile(source, temporary); os.replace(temporary, audio)
        manifest = self.root / f"{key}.json"; temp_manifest = manifest.with_suffix(".tmp")
        temp_manifest.write_text(json.dumps({
            "provider": result.provider, "duration_ms": result.duration_ms,
            "input_units": result.usage.input_units, "output_units": result.usage.output_units,
        }), encoding="utf-8"); os.replace(temp_manifest, manifest)


class CachedTtsProvider:
    def __init__(self, upstream: TtsProvider, cache: TtsCache, *, model: str, provider_version: str) -> None:
        self.upstream, self.cache, self.model, self.provider_version = upstream, cache, model, provider_version

    async def synthesize(self, request: TtsRequest) -> TtsResult:
        key = self.cache.key(request, model=self.model, provider_version=self.provider_version)
        cached = self.cache.get(key)
        if cached is None:
            result = await self.upstream.synthesize(request)
            self.cache.put(key, result.audio_path, result)
            return result
        source, manifest = cached
        root = request.output_root.resolve(); root.mkdir(parents=True, exist_ok=True)
        output = (root / request.filename).resolve()
        if not output.is_relative_to(root): raise ValueError("TTS output escapes requested root")
        temporary = output.with_suffix(output.suffix + ".tmp")
        shutil.copyfile(source, temporary); os.replace(temporary, output)
        return TtsResult(
            provider=manifest["provider"], audio_path=output,
            duration_ms=int(manifest["duration_ms"]),
            usage=ProviderUsage(input_units=int(manifest["input_units"]), output_units=int(manifest["output_units"])),
        )
