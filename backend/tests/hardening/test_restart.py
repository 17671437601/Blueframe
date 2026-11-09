from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

from blueframe.jobs.repository import JobRepository
from blueframe.media.probe import MediaInfo
from blueframe.rendering.artifacts import RenderArtifactRepository
from blueframe.rendering.graph import RenderInput, RenderSegment, RenderSpec
from blueframe.rendering.service import RenderService
from blueframe.workers.protocol import JobResult
from blueframe.workers.recovery import recover_expired_leases
from blueframe.workers.runner import WorkerRunner


class Control:
    pause_requested = False
    cancel_requested = False

    def checkpoint(self, value): pass
    def progress(self, value, stage=None): pass
    def heartbeat(self): pass


class FakeExecutor:
    def run(self, command, *, on_output, should_stop):
        Path(command[-1]).parent.mkdir(parents=True, exist_ok=True)
        Path(command[-1]).write_bytes(b"restarted-video")
        on_output("out_time_ms=1000000\nprogress=end\n")
        return 0


class ResumableHandler:
    def __init__(self) -> None:
        self.seen: list[dict | None] = []

    def run(self, job, checkpoint, control) -> JobResult:
        self.seen.append(checkpoint)
        control.progress(100, "resumed")
        return JobResult()


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


def test_restart_requeues_the_job_and_resumes_from_the_persisted_checkpoint(
    migrated_session_factory,
) -> None:
    started = datetime(2026, 11, 9, tzinfo=UTC)
    repository = JobRepository(migrated_session_factory, clock=lambda: started)
    job = repository.create("render", {}, "restart-checkpoint")
    claimed = repository.claim_next("old-worker", lease_seconds=30)
    assert claimed is not None
    repository.save_checkpoint(
        claimed.id, "old-worker", {"stage": "rendered", "artifact_id": "artifact-1"}
    )

    later = started + timedelta(seconds=31)
    recovered = recover_expired_leases(
        JobRepository(migrated_session_factory, clock=lambda: later),
        now=later, max_attempts=3,
    )
    assert recovered == 1

    handler = ResumableHandler()
    runner = WorkerRunner(
        JobRepository(migrated_session_factory, clock=lambda: later),
        {"render": handler}, worker_id="new-worker", lease_seconds=30,
    )
    assert runner.run_once() is True

    assert handler.seen == [{"stage": "rendered", "artifact_id": "artifact-1"}]
    assert repository.get(job.id).status.value == "completed"


def test_restart_rerenders_an_artifact_left_in_progress(
    migrated_session_factory, tmp_path: Path,
) -> None:
    repository = RenderArtifactRepository(migrated_session_factory)
    repository.start(
        job_id="crashed-job", project_id="project-1", plan_id="plan-1",
        spec_hash="stale-hash", working_path=tmp_path / "render.partial.mp4",
    )
    service = RenderService(repository, executor=FakeExecutor(), probe=media_info)

    completed = service.render(
        job_id="restarted-job", project_id="project-1", plan_id="plan-1",
        spec=spec(tmp_path), control=Control(),
    )

    assert completed.status == "completed"
    assert completed.published_path == spec(tmp_path).output
    assert completed.published_path.read_bytes() == b"restarted-video"
