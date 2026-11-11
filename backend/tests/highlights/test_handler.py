from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

from blueframe.asr.repository import AsrRepository
from blueframe.highlights.handler import HighlightBatchHandler
from blueframe.highlights.models import HighlightClipSpec
from blueframe.highlights.repository import HighlightBatchRepository
from blueframe.jobs.models import Job, JobStatus
from blueframe.projects.models import ProjectType, SourceRegistration
from blueframe.projects.repository import ProjectRepository


class FakeRender:
    def __init__(self, fail_calls=()):
        self.calls: list[str] = []
        self.fail_calls = set(fail_calls)

    def render(self, *, job_id, project_id, plan_id, spec, control):
        index = len(self.calls)
        self.calls.append(plan_id)
        if index in self.fail_calls:
            raise RuntimeError("ffmpeg failed")
        return SimpleNamespace(status="completed", published_path=spec.output)


class Control:
    pause_requested = cancel_requested = False

    def __init__(self):
        self.values: list[tuple[float, str | None]] = []

    def progress(self, value, stage=None):
        self.values.append((value, stage))

    def heartbeat(self):
        pass

    def checkpoint(self, _value):
        pass


def setup_batch(session_factory, tmp_path: Path, count=3):
    projects = ProjectRepository(session_factory)
    project = projects.create(
        name="Drama", project_type=ProjectType.DRAMA, root_path=tmp_path,
        output_relative_path="out", config={}, idempotency_key="highlight-project",
    )
    source = tmp_path / "ep1.mp4"
    source.write_bytes(b"episode")
    registered = projects.add_sources(
        project.id,
        [SourceRegistration(relative_path="ep1.mp4", size_bytes=7, modified_ns=1, content_fingerprint="f")],
    )[0]
    projects.update_media_info(registered.id, {"duration_ms": 120_000, "has_audio": True, "rotation": 0})
    batches = HighlightBatchRepository(session_factory)
    specs = tuple(
        HighlightClipSpec(
            title=f"高光 {index}", reason="冲突集中", score=90 - index,
            source_id=registered.id, start_ms=index * 20_000, end_ms=index * 20_000 + 10_000,
        )
        for index in range(count)
    )
    batch = batches.create(
        project_id=project.id, analysis_version_id="analysis-1", specs=specs,
        target_count=count, min_duration_ms=8_000, max_duration_ms=20_000, burn_subtitles=False,
    )
    return projects, batches, batch


def job(batch_id: str) -> Job:
    now = datetime.now(UTC)
    return Job(
        id="job", job_type="render_highlights", payload={"batch_id": batch_id},
        status=JobStatus.RUNNING, progress=0, attempts=0, idempotency_key="highlight",
        created_at=now, updated_at=now,
    )


def test_batch_keeps_partial_success_and_retries_only_failed_clip(
    migrated_session_factory, tmp_path: Path
) -> None:
    projects, batches, batch = setup_batch(migrated_session_factory, tmp_path)
    asr = AsrRepository(migrated_session_factory)
    first = FakeRender(fail_calls={1})
    HighlightBatchHandler(projects, batches, asr, first, Path("ffmpeg")).run(
        job(batch.id), None, Control()
    )

    partial = batches.get(batch.id)
    assert partial.status == "partial"
    assert [clip.status for clip in partial.clips] == ["completed", "failed", "completed"]
    assert partial.clips[0].output_path is not None
    assert partial.clips[1].error_summary == "ffmpeg failed"

    batches.retry_failed(batch.id)
    second = FakeRender()
    HighlightBatchHandler(projects, batches, asr, second, Path("ffmpeg")).run(
        job(batch.id), None, Control()
    )

    final = batches.get(batch.id)
    assert len(second.calls) == 1
    assert final.status == "completed"
    assert all(clip.status == "completed" for clip in final.clips)


def test_pause_stops_at_clip_boundary(migrated_session_factory, tmp_path: Path) -> None:
    projects, batches, batch = setup_batch(migrated_session_factory, tmp_path)
    control = Control()
    render = FakeRender()
    handler = HighlightBatchHandler(
        projects, batches, AsrRepository(migrated_session_factory), render, Path("ffmpeg")
    )
    original = render.render

    def render_once(**kwargs):
        result = original(**kwargs)
        control.pause_requested = True
        return result

    render.render = render_once
    handler.run(job(batch.id), None, control)

    paused = batches.get(batch.id)
    assert paused.status == "paused"
    assert [clip.status for clip in paused.clips] == ["completed", "queued", "queued"]
