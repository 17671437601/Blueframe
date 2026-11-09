from __future__ import annotations

import errno
from pathlib import Path

import pytest
from sqlalchemy import text

from blueframe.jobs.repository import JobRepository
from blueframe.media.probe import MediaInfo
from blueframe.rendering.artifacts import RenderArtifactRepository
from blueframe.rendering.graph import RenderInput, RenderSegment, RenderSpec
from blueframe.rendering.service import RenderService
from blueframe.workers.protocol import JobResult
from blueframe.workers.runner import WorkerRunner


class Control:
    pause_requested = False
    cancel_requested = False

    def checkpoint(self, value): pass
    def progress(self, value, stage=None): pass
    def heartbeat(self): pass


class DiskFullExecutor:
    def run(self, command, *, on_output, should_stop):
        raise OSError(errno.ENOSPC, "No space left on device")


class DiskFullHandler:
    def run(self, job, checkpoint, control) -> JobResult:
        raise OSError(errno.ENOSPC, "No space left on device")


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


def _latest_artifact_status(session_factory) -> str:
    with session_factory() as session:
        return session.execute(
            text("SELECT status FROM render_artifacts ORDER BY created_at DESC LIMIT 1")
        ).scalar_one()


def test_disk_full_marks_artifact_failed_and_preserves_prior_publish(
    migrated_session_factory, tmp_path: Path,
) -> None:
    target = spec(tmp_path).output
    target.parent.mkdir(parents=True)
    target.write_bytes(b"prior-video")
    repository = RenderArtifactRepository(migrated_session_factory)
    service = RenderService(repository, executor=DiskFullExecutor(), probe=media_info)

    with pytest.raises(OSError) as error:
        service.render(
            job_id="job-full", project_id="project-1", plan_id="plan-full",
            spec=spec(tmp_path), control=Control(),
        )

    assert error.value.errno == errno.ENOSPC
    assert target.read_bytes() == b"prior-video"
    assert not target.with_suffix(".manifest.json").exists()
    assert _latest_artifact_status(migrated_session_factory) == "failed"


def test_worker_fails_job_instead_of_leaving_it_running_when_disk_is_full(
    migrated_session_factory,
) -> None:
    repository = JobRepository(migrated_session_factory)
    job = repository.create("render", {}, "disk-full")
    runner = WorkerRunner(
        repository, {"render": DiskFullHandler()}, worker_id="worker", lease_seconds=30,
    )

    assert runner.run_once() is True

    failed = repository.get(job.id)
    assert failed.status.value == "failed"
    assert failed.error_code == "handler_error"
    assert "No space left on device" in failed.error_summary
