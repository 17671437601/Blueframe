from __future__ import annotations

from pathlib import Path
from typing import Callable

from blueframe.media.tools import (
    CommandRunner,
    ExecutableSet,
    MediaToolError,
    SubprocessRunner,
)


def audio_extraction_arguments(
    tools: ExecutableSet, source: Path, output: Path
) -> tuple[str, ...]:
    return (
        str(tools.ffmpeg), "-hide_banner", "-loglevel", "error", "-y",
        "-i", str(source), "-vn", "-ac", "1", "-ar", "16000", str(output),
    )


def thumbnail_arguments(
    tools: ExecutableSet, source: Path, output: Path, *, at_ms: int
) -> tuple[str, ...]:
    return (
        str(tools.ffmpeg), "-hide_banner", "-loglevel", "error", "-y",
        "-ss", f"{max(0, at_ms) / 1000:.3f}", "-i", str(source),
        "-frames:v", "1", "-q:v", "3", str(output),
    )


def proxy_arguments(
    tools: ExecutableSet, source: Path, output: Path, *, max_height: int = 720
) -> tuple[str, ...]:
    return (
        str(tools.ffmpeg), "-hide_banner", "-loglevel", "error", "-y",
        "-i", str(source), "-vf", f"scale=-2:min({max_height},ih)",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "26",
        "-c:a", "aac", "-b:a", "96k", "-movflags", "+faststart", str(output),
    )


def extract_audio(
    tools: ExecutableSet,
    source: Path,
    output: Path,
    *,
    runner: CommandRunner | None = None,
) -> Path:
    return _execute(audio_extraction_arguments(tools, source, output), output, runner, 3600)


def create_thumbnail(
    tools: ExecutableSet,
    source: Path,
    output: Path,
    *,
    at_ms: int = 1000,
    runner: CommandRunner | None = None,
) -> Path:
    return _execute(thumbnail_arguments(tools, source, output, at_ms=at_ms), output, runner, 120)


def create_proxy(
    tools: ExecutableSet,
    source: Path,
    output: Path,
    *,
    max_height: int = 720,
    runner: CommandRunner | None = None,
) -> Path:
    return _execute(proxy_arguments(tools, source, output, max_height=max_height), output, runner, 7200)


def _execute(
    arguments: tuple[str, ...],
    output: Path,
    runner: CommandRunner | None,
    timeout: float,
) -> Path:
    output.parent.mkdir(parents=True, exist_ok=True)
    result = (runner or SubprocessRunner()).run(arguments, timeout=timeout)
    if result.returncode != 0:
        raise MediaToolError("媒体处理失败，请检查源文件和可用磁盘空间")
    if not output.is_file() and runner is None:
        raise MediaToolError("媒体工具未生成预期文件")
    return output
