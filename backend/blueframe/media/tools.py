from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, Sequence


@dataclass(frozen=True)
class ExecutableSet:
    ffmpeg: Path
    ffprobe: Path


@dataclass(frozen=True)
class ProcessResult:
    returncode: int
    stdout: str
    stderr: str


class CommandRunner(Protocol):
    def run(self, arguments: Sequence[str | Path], *, timeout: float) -> ProcessResult: ...


class MediaToolError(RuntimeError):
    pass


class SubprocessRunner:
    def run(
        self, arguments: Sequence[str | Path], *, timeout: float
    ) -> ProcessResult:
        try:
            completed = subprocess.run(
                [str(argument) for argument in arguments],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=timeout,
                check=False,
                shell=False,
                creationflags=(
                    subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
                ),
            )
        except subprocess.TimeoutExpired as error:
            raise MediaToolError("媒体工具执行超时") from error
        except OSError as error:
            raise MediaToolError("无法启动本地媒体工具") from error
        return ProcessResult(completed.returncode, completed.stdout, completed.stderr)


def discover_executables(
    *, search_roots: Sequence[Path] = (), explicit_dir: Path | None = None
) -> ExecutableSet:
    configured = explicit_dir
    if configured is None and os.environ.get("BLUEFRAME_FFMPEG_DIR"):
        configured = Path(os.environ["BLUEFRAME_FFMPEG_DIR"])
    directories: list[Path] = []
    if configured is not None:
        directories.append(configured)
    for root in search_roots:
        directories.extend(
            [root / "_internal" / "ffmpeg" / "bin", root / "ffmpeg" / "bin", root / "bin"]
        )
    names = ("ffmpeg.exe", "ffprobe.exe") if os.name == "nt" else ("ffmpeg", "ffprobe")
    for directory in directories:
        ffmpeg = directory / names[0]
        ffprobe = directory / names[1]
        if ffmpeg.is_file() and ffprobe.is_file():
            return ExecutableSet(ffmpeg.resolve(), ffprobe.resolve())
    raise MediaToolError("未找到 FFmpeg/FFprobe，请在设置中配置媒体工具目录")
