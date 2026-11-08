from __future__ import annotations

import json
from pathlib import Path

import pytest

from blueframe.media.probe import MediaProbeError, probe_media
from blueframe.media.tools import ExecutableSet, ProcessResult


class FakeRunner:
    def __init__(self, result: ProcessResult) -> None:
        self.result = result
        self.calls: list[tuple[str, ...]] = []

    def run(self, arguments, *, timeout):
        self.calls.append(tuple(str(item) for item in arguments))
        return self.result


def test_probe_parses_video_audio_rotation_and_preserves_unicode_argument(tmp_path: Path) -> None:
    source = tmp_path / "中文 空格" / "第一集.mp4"
    payload = {
        "format": {"duration": "12.345", "size": "54321", "format_name": "mov,mp4"},
        "streams": [
            {
                "codec_type": "video", "codec_name": "h264", "width": 1920, "height": 1080,
                "avg_frame_rate": "30000/1001", "tags": {"rotate": "90"},
            },
            {"codec_type": "audio", "codec_name": "aac", "sample_rate": "48000", "channels": 2},
        ],
    }
    runner = FakeRunner(ProcessResult(0, json.dumps(payload), ""))

    info = probe_media(source, ExecutableSet(Path("ffmpeg"), Path("ffprobe")), runner=runner)

    assert info.duration_ms == 12345
    assert info.width == 1920 and info.height == 1080
    assert info.rotation == 90
    assert info.frame_rate == pytest.approx(29.970, rel=0.001)
    assert info.has_audio is True and info.audio_codec == "aac"
    assert str(source) in runner.calls[0]
    assert runner.calls[0][0] == "ffprobe"


def test_probe_represents_no_audio_and_rejects_damaged_media(tmp_path: Path) -> None:
    video_only = FakeRunner(
        ProcessResult(
            0,
            json.dumps({
                "format": {"duration": "2.0", "size": "10", "format_name": "mp4"},
                "streams": [{"codec_type": "video", "codec_name": "h264", "width": 720, "height": 1280, "avg_frame_rate": "25/1"}],
            }),
            "",
        )
    )
    info = probe_media(tmp_path / "silent.mp4", ExecutableSet(Path("ffmpeg"), Path("ffprobe")), runner=video_only)
    assert info.has_audio is False
    assert info.audio_codec is None

    broken = FakeRunner(ProcessResult(1, "", "private C:/Users/name/broken.mp4 invalid data"))
    with pytest.raises(MediaProbeError, match="无法读取媒体信息") as error:
        probe_media(tmp_path / "broken.mp4", ExecutableSet(Path("ffmpeg"), Path("ffprobe")), runner=broken)
    assert "C:/Users" not in str(error.value)
