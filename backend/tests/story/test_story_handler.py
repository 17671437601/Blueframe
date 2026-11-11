from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

from blueframe.asr.repository import AsrRepository
from blueframe.editing.models import EditPlanDraft, EditSegment, PlanKind
from blueframe.editing.repository import EditPlanRepository
from blueframe.jobs.models import Job, JobStatus
from blueframe.projects.models import ProjectType, SourceRegistration
from blueframe.projects.repository import ProjectRepository
from blueframe.story.handler import StoryBatchHandler
from blueframe.story.models import StoryPlanSpec, StorySegmentSpec
from blueframe.story.repository import StoryBatchRepository


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
        output_relative_path="out", config={}, idempotency_key="story-project",
    )
    source = tmp_path / "ep1.mp4"
    source.write_bytes(b"episode")
    registered = projects.add_sources(
        project.id,
        [SourceRegistration(relative_path="ep1.mp4", size_bytes=7, modified_ns=1, content_fingerprint="f")],
    )[0]
    projects.update_media_info(registered.id, {"duration_ms": 600_000, "has_audio": True, "rotation": 0})
    batches = StoryBatchRepository(session_factory)
    plans = EditPlanRepository(session_factory)
    specs = tuple(
        StoryPlanSpec(
            title=f"主线成片 {index + 1}",
            target_duration_ms=90_000,
            segments=(
                StorySegmentSpec(
                    source_id=registered.id,
                    start_ms=index * 60_000,
                    end_ms=index * 60_000 + 60_000,
                ),
            ),
        )
        for index in range(count)
    )
    batch = batches.create(
        project_id=project.id, analysis_version_id="analysis-1", specs=specs,
        target_count=count, min_duration_ms=60_000, max_duration_ms=120_000, burn_subtitles=False,
    )
    for item, spec in zip(batch.items, specs, strict=False):
        plan = plans.save(
            project.id,
            EditPlanDraft(
                title=spec.title, kind=PlanKind.STORY,
                target_duration_ms=spec.target_duration_ms, segments=tuple(
                    EditSegment(
                        source_id=segment.source_id, source_start_ms=segment.start_ms,
                        source_end_ms=segment.end_ms, source_duration_ms=600_000,
                    )
                    for segment in spec.segments
                ),
            ),
            idempotency_key=f"story:{batch.id}:{item.item_index}",
        )
        batches.attach_plan(item.id, plan.id)
    return projects, batches, plans, batch


def job(batch_id: str) -> Job:
    now = datetime.now(UTC)
    return Job(
        id="job", job_type="render_story_batch", payload={"batch_id": batch_id},
        status=JobStatus.RUNNING, progress=0, attempts=0, idempotency_key="story",
        created_at=now, updated_at=now,
    )


def test_batch_keeps_partial_success_and_retries_only_failed_item(
    migrated_session_factory, tmp_path: Path
) -> None:
    projects, batches, plans, batch = setup_batch(migrated_session_factory, tmp_path)
    asr = AsrRepository(migrated_session_factory)
    first = FakeRender(fail_calls={1})
    StoryBatchHandler(projects, batches, plans, asr, first, Path("ffmpeg")).run(
        job(batch.id), None, Control()
    )

    partial = batches.get(batch.id)
    assert partial.status == "partial"
    assert [item.status for item in partial.items] == ["completed", "failed", "completed"]
    assert partial.items[1].error_summary == "ffmpeg failed"

    batches.retry_failed(batch.id)
    second = FakeRender()
    StoryBatchHandler(projects, batches, plans, asr, second, Path("ffmpeg")).run(
        job(batch.id), None, Control()
    )

    final = batches.get(batch.id)
    assert len(second.calls) == 1
    assert final.status == "completed"
    assert all(item.status == "completed" for item in final.items)


def test_pause_stops_at_item_boundary(migrated_session_factory, tmp_path: Path) -> None:
    projects, batches, plans, batch = setup_batch(migrated_session_factory, tmp_path)
    control = Control()
    render = FakeRender()
    handler = StoryBatchHandler(
        projects, batches, plans, AsrRepository(migrated_session_factory), render, Path("ffmpeg")
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
    assert [item.status for item in paused.items] == ["completed", "queued", "queued"]
