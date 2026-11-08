from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from blueframe.media.probe import probe_media
from blueframe.media.tools import discover_executables
from blueframe.rendering.artifacts import RenderArtifactRepository
from blueframe.rendering.graph import RenderInput, RenderSegment, RenderSpec
from blueframe.rendering.service import FfmpegExecutor, RenderService


class Control:
    pause_requested = False
    cancel_requested = False
    def heartbeat(self): pass
    def checkpoint(self, _value): pass
    def progress(self, _value, _stage=None): pass


def test_real_ffmpeg_renders_mixed_audio_golden_media(migrated_session_factory, tmp_path: Path) -> None:
    repository_root = Path(__file__).resolve().parents[4]
    try:
        tools = discover_executables(search_roots=[repository_root])
    except FileNotFoundError:
        pytest.skip("bundled FFmpeg is unavailable")
    first = tmp_path / "有声.mp4"
    second = tmp_path / "静音.mp4"
    narration = tmp_path / "解说.mp3"
    subprocess.run([
        str(tools.ffmpeg), "-hide_banner", "-loglevel", "error", "-y",
        "-f", "lavfi", "-i", "color=c=red:s=640x360:d=1",
        "-f", "lavfi", "-i", "sine=frequency=440:duration=1",
        "-shortest", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", str(first),
    ], check=True)
    subprocess.run([
        str(tools.ffmpeg), "-hide_banner", "-loglevel", "error", "-y",
        "-f", "lavfi", "-i", "sine=frequency=880:duration=1.6",
        "-c:a", "libmp3lame", str(narration),
    ], check=True)
    subprocess.run([
        str(tools.ffmpeg), "-hide_banner", "-loglevel", "error", "-y",
        "-f", "lavfi", "-i", "color=c=blue:s=360x640:d=1",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", str(second),
    ], check=True)
    output = tmp_path / "交付" / "golden.mp4"
    service = RenderService(
        RenderArtifactRepository(migrated_session_factory), executor=FfmpegExecutor(),
        probe=lambda path: probe_media(path, tools), hardware_encoder=None,
    )
    artifact = service.render(
        job_id="golden-job", project_id="golden-project", plan_id="golden-plan",
        spec=RenderSpec(
            ffmpeg=tools.ffmpeg, output=output, width=720, height=1280, fps=25,
            inputs=(
                RenderInput(source_id="one", path=first, has_audio=True),
                RenderInput(source_id="two", path=second, has_audio=False),
            ),
            segments=(
                RenderSegment(source_id="one", start_ms=0, end_ms=800),
                RenderSegment(source_id="two", start_ms=0, end_ms=800),
            ),
            narration_path=narration,
        ), control=Control(),
    )
    info = probe_media(output, tools)
    assert artifact.status == "completed"
    assert 1400 <= info.duration_ms <= 1900
    assert (info.width, info.height, info.has_audio) == (720, 1280, True)
