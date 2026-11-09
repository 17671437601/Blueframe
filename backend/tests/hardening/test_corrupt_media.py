from __future__ import annotations

from pathlib import Path

import pytest

from blueframe.media.probe import MediaProbeError, probe_media
from blueframe.media.tools import (
    ExecutableSet,
    MediaToolError,
    ProcessResult,
    discover_executables,
)


def available_tools() -> ExecutableSet:
    try:
        return discover_executables(search_roots=[Path(__file__).resolve().parents[4]])
    except MediaToolError:
        pytest.skip("FFmpeg/FFprobe is not available on this machine")


def test_corrupt_and_empty_media_are_rejected_without_crashing(tmp_path: Path) -> None:
    tools = available_tools()
    corrupt = tmp_path / "损坏 素材.mp4"
    corrupt.write_bytes(b"not-a-real-video" * 4096)
    with pytest.raises(MediaProbeError, match="损坏或格式不受支持"):
        probe_media(corrupt, tools, timeout=20)

    empty = tmp_path / "empty.mp4"
    empty.write_bytes(b"")
    with pytest.raises(MediaProbeError):
        probe_media(empty, tools, timeout=20)


class TimeoutRunner:
    def run(self, arguments, *, timeout: float):
        raise MediaToolError("媒体工具执行超时")


def test_probe_timeout_surfaces_a_typed_error(tmp_path: Path) -> None:
    media = tmp_path / "slow.mp4"
    media.write_bytes(b"video")
    with pytest.raises(MediaToolError, match="超时"):
        probe_media(
            media, ExecutableSet(Path("ffmpeg"), Path("ffprobe")),
            runner=TimeoutRunner(), timeout=1,
        )


class IncompleteRunner:
    def run(self, arguments, *, timeout: float) -> ProcessResult:
        return ProcessResult(0, '{"format": {"duration": "1.0"}}', "")


def test_incomplete_probe_payload_is_reported_as_media_error(tmp_path: Path) -> None:
    media = tmp_path / "odd.mp4"
    media.write_bytes(b"video")
    with pytest.raises(MediaProbeError, match="探测结果不完整"):
        probe_media(
            media, ExecutableSet(Path("ffmpeg"), Path("ffprobe")),
            runner=IncompleteRunner(), timeout=5,
        )
