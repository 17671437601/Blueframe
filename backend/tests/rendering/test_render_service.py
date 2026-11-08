from __future__ import annotations

from pathlib import Path

import pytest

from blueframe.media.probe import MediaInfo
from blueframe.rendering.artifacts import RenderArtifactRepository
from blueframe.rendering.graph import RenderInput, RenderSegment, RenderSpec
from blueframe.rendering.service import RenderService


class Control:
    pause_requested = False
    cancel_requested = False

    def __init__(self): self.checkpoints = []; self.progress_values = []
    def checkpoint(self, value): self.checkpoints.append(value)
    def progress(self, value, stage=None): self.progress_values.append((value, stage))
    def heartbeat(self): pass


class FakeExecutor:
    def __init__(self, exit_codes=(0,)) -> None:
        self.exit_codes = list(exit_codes)
        self.calls = []

    def run(self, command, *, on_output, should_stop):
        self.calls.append(command)
        Path(command[-1]).parent.mkdir(parents=True, exist_ok=True)
        Path(command[-1]).write_bytes(b"new-video")
        on_output("out_time_ms=1000000\nprogress=end\n")
        return self.exit_codes.pop(0)


def media_info(path: Path) -> MediaInfo:
    return MediaInfo(
        duration_ms=2000, size_bytes=path.stat().st_size,
        format_name="mp4", width=1080, height=1920, rotation=0, frame_rate=30,
        video_codec="h264", has_audio=True, audio_codec="aac",
        audio_sample_rate=48000, audio_channels=2,
    )


def spec(tmp_path: Path) -> RenderSpec:
    return RenderSpec(
        ffmpeg=Path("ffmpeg"), output=tmp_path / "delivery" / "成片.mp4",
        width=1080, height=1920, fps=30,
        inputs=(RenderInput(source_id="s1", path=tmp_path / "input.mp4", has_audio=True),),
        segments=(RenderSegment(source_id="s1", start_ms=0, end_ms=2000),),
    )


def test_render_falls_back_validates_atomically_publishes_and_reuses(
    migrated_session_factory, tmp_path: Path,
) -> None:
    target = spec(tmp_path).output
    target.parent.mkdir(parents=True)
    target.write_bytes(b"prior-video")
    executor = FakeExecutor(exit_codes=(1, 0))
    service = RenderService(
        RenderArtifactRepository(migrated_session_factory), executor=executor, probe=media_info,
    )
    control = Control()

    first = service.render(job_id="job-1", project_id="project-1", plan_id="plan-1", spec=spec(tmp_path), control=control)
    second = service.render(job_id="job-2", project_id="project-1", plan_id="plan-1", spec=spec(tmp_path), control=Control())

    assert first.status == second.status == "completed"
    assert target.read_bytes() == b"new-video"
    assert len(executor.calls) == 2
    assert target.with_suffix(".manifest.json").exists()
    assert control.progress_values[-1][0] == 100


def test_invalid_output_preserves_prior_publish(migrated_session_factory, tmp_path: Path) -> None:
    target = spec(tmp_path).output
    target.parent.mkdir(parents=True)
    target.write_bytes(b"prior-video")
    executor = FakeExecutor()

    def invalid(_path):
        raise ValueError("damaged output")

    service = RenderService(RenderArtifactRepository(migrated_session_factory), executor=executor, probe=invalid)
    with pytest.raises(ValueError, match="damaged"):
        service.render(job_id="job-bad", project_id="project-1", plan_id="plan-bad", spec=spec(tmp_path), control=Control())
    assert target.read_bytes() == b"prior-video"


def test_pause_before_render_checkpoints_without_publishing(migrated_session_factory, tmp_path: Path) -> None:
    control = Control(); control.pause_requested = True
    executor = FakeExecutor()
    result = RenderService(
        RenderArtifactRepository(migrated_session_factory), executor=executor, probe=media_info,
    ).render(job_id="job-pause", project_id="project-1", plan_id="plan-pause", spec=spec(tmp_path), control=control)
    assert result.status == "paused"
    assert executor.calls == []
    assert control.checkpoints[-1]["stage"] == "waiting_to_render"
