from __future__ import annotations

import json
from fractions import Fraction
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from blueframe.media.tools import CommandRunner, ExecutableSet, SubprocessRunner


class MediaProbeError(RuntimeError):
    pass


class MediaInfo(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    duration_ms: int = Field(ge=0)
    size_bytes: int = Field(ge=0)
    format_name: str
    width: int = Field(gt=0)
    height: int = Field(gt=0)
    rotation: int
    frame_rate: float = Field(ge=0)
    video_codec: str
    has_audio: bool
    audio_codec: str | None
    audio_sample_rate: int | None
    audio_channels: int | None


def probe_media(
    path: Path,
    tools: ExecutableSet,
    *,
    runner: CommandRunner | None = None,
    timeout: float = 30,
) -> MediaInfo:
    command_runner = runner or SubprocessRunner()
    result = command_runner.run(
        (
            tools.ffprobe,
            "-v", "error",
            "-print_format", "json",
            "-show_format",
            "-show_streams",
            path,
        ),
        timeout=timeout,
    )
    if result.returncode != 0:
        raise MediaProbeError("无法读取媒体信息：文件可能损坏或格式不受支持")
    try:
        payload = json.loads(result.stdout)
        streams = payload.get("streams", [])
        video = next(stream for stream in streams if stream.get("codec_type") == "video")
        audio = next(
            (stream for stream in streams if stream.get("codec_type") == "audio"),
            None,
        )
        format_info = payload.get("format", {})
        return MediaInfo(
            duration_ms=max(0, round(float(format_info.get("duration", 0)) * 1000)),
            size_bytes=max(0, int(format_info.get("size", 0))),
            format_name=str(format_info.get("format_name", "unknown")),
            width=int(video["width"]),
            height=int(video["height"]),
            rotation=_rotation(video),
            frame_rate=_frame_rate(video.get("avg_frame_rate", "0/1")),
            video_codec=str(video.get("codec_name", "unknown")),
            has_audio=audio is not None,
            audio_codec=None if audio is None else str(audio.get("codec_name", "unknown")),
            audio_sample_rate=None if audio is None else int(audio.get("sample_rate", 0)),
            audio_channels=None if audio is None else int(audio.get("channels", 0)),
        )
    except (KeyError, TypeError, ValueError, StopIteration, json.JSONDecodeError) as error:
        raise MediaProbeError("无法读取媒体信息：探测结果不完整") from error


def _frame_rate(value: str) -> float:
    fraction = Fraction(value)
    return 0.0 if fraction.denominator == 0 else float(fraction)


def _rotation(video: dict[str, Any]) -> int:
    tags = video.get("tags") or {}
    if "rotate" in tags:
        return int(float(tags["rotate"])) % 360
    for side_data in video.get("side_data_list") or []:
        if "rotation" in side_data:
            return int(float(side_data["rotation"])) % 360
    return 0
