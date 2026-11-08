from __future__ import annotations

from pathlib import Path

from blueframe.media.preview import (
    audio_extraction_arguments,
    proxy_arguments,
    thumbnail_arguments,
)
from blueframe.media.tools import ExecutableSet


TOOLS = ExecutableSet(Path("C:/tools/ffmpeg.exe"), Path("C:/tools/ffprobe.exe"))


def test_preview_commands_are_argument_arrays_with_safe_defaults(tmp_path: Path) -> None:
    source = tmp_path / "中文 素材.mp4"
    audio = tmp_path / "work" / "audio.wav"
    thumbnail = tmp_path / "work" / "cover.jpg"
    proxy = tmp_path / "work" / "proxy.mp4"

    audio_args = audio_extraction_arguments(TOOLS, source, audio)
    thumb_args = thumbnail_arguments(TOOLS, source, thumbnail, at_ms=1500)
    proxy_args = proxy_arguments(TOOLS, source, proxy, max_height=720)

    assert audio_args[0] == str(TOOLS.ffmpeg)
    assert audio_args[audio_args.index("-i") + 1] == str(source)
    assert audio_args[-6:] == ("-vn", "-ac", "1", "-ar", "16000", str(audio))
    assert "1.500" in thumb_args
    assert thumb_args[-1] == str(thumbnail)
    assert "scale=-2:min(720,ih)" in proxy_args
    assert proxy_args[-1] == str(proxy)


def test_discovery_can_use_sibling_packaged_runtime(tmp_path: Path) -> None:
    from blueframe.media.tools import discover_executables

    bin_dir = tmp_path / "_internal" / "ffmpeg" / "bin"
    bin_dir.mkdir(parents=True)
    (bin_dir / "ffmpeg.exe").touch()
    (bin_dir / "ffprobe.exe").touch()

    tools = discover_executables(search_roots=[tmp_path])

    assert tools.ffmpeg == (bin_dir / "ffmpeg.exe").resolve()
    assert tools.ffprobe == (bin_dir / "ffprobe.exe").resolve()
