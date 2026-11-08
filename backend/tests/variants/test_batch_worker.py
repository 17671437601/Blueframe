from datetime import UTC, datetime
from pathlib import Path

from blueframe.jobs.handlers.variants import VariantBatchHandler
from blueframe.jobs.models import Job, JobStatus
from blueframe.projects.models import ProjectType, SourceRegistration
from blueframe.projects.repository import ProjectRepository
from blueframe.variants.models import generate_recipe
from blueframe.variants.repository import VariantBatchRepository


class Executor:
    def __init__(self, fail_indexes=()): self.calls, self.fail_indexes = 0, set(fail_indexes)
    def run(self, command, *, on_output, should_stop):
        index = self.calls; self.calls += 1
        if index in self.fail_indexes: return 1
        Path(command[-1]).write_bytes(b"video"); on_output("out_time_ms=500000\n"); return 0


class Control:
    pause_requested = cancel_requested = False
    def __init__(self): self.values = []
    def progress(self, value, stage=None): self.values.append((value, stage))
    def heartbeat(self): pass
    def checkpoint(self, _value): pass


def setup_batch(session_factory, tmp_path: Path, count=3):
    projects = ProjectRepository(session_factory)
    project = projects.create(name="Variants", project_type=ProjectType.VARIANTS, root_path=tmp_path, output_relative_path="out", config={}, idempotency_key="variant-project")
    source = tmp_path / "master.mp4"; source.write_bytes(b"master")
    registered = projects.add_sources(project.id, [SourceRegistration(relative_path="master.mp4", size_bytes=6, modified_ns=1, content_fingerprint="f")])[0]
    projects.update_media_info(registered.id, {"duration_ms": 1000, "has_audio": True, "rotation": 0})
    repo = VariantBatchRepository(session_factory)
    batch = repo.create(project_id=project.id, source_id=registered.id, recipes=tuple(generate_recipe(seed=9, index=i, width=720, height=1280) for i in range(count)))
    return projects, repo, batch


def job(batch_id):
    now = datetime.now(UTC)
    return Job(id="job", job_type="render_variant_batch", payload={"batch_id": batch_id}, status=JobStatus.RUNNING, progress=0, attempts=0, idempotency_key="batch", created_at=now, updated_at=now)


def test_batch_keeps_partial_success_and_retry_only_runs_failed_item(migrated_session_factory, tmp_path: Path) -> None:
    projects, repo, batch = setup_batch(migrated_session_factory, tmp_path)
    first_executor = Executor(fail_indexes={1})
    handler = VariantBatchHandler(projects, repo, first_executor, Path("ffmpeg"), probe=lambda path: path.stat().st_size)
    handler.run(job(batch.id), None, Control())
    first = repo.get(batch.id)
    assert first.status == "partial"
    assert [item.status for item in first.items] == ["completed", "failed", "completed"]

    repo.retry_failed(batch.id)
    second_executor = Executor()
    VariantBatchHandler(projects, repo, second_executor, Path("ffmpeg"), probe=lambda path: path.stat().st_size).run(job(batch.id), None, Control())
    final = repo.get(batch.id)
    assert second_executor.calls == 1
    assert final.status == "completed"
    assert all(item.status == "completed" for item in final.items)


def test_batch_cancellation_stops_at_item_boundary(migrated_session_factory, tmp_path: Path) -> None:
    projects, repo, batch = setup_batch(migrated_session_factory, tmp_path)
    control = Control()
    class CancellingExecutor(Executor):
        def run(self, command, *, on_output, should_stop):
            result = super().run(command, on_output=on_output, should_stop=should_stop)
            control.cancel_requested = True
            return result
    VariantBatchHandler(projects, repo, CancellingExecutor(), Path("ffmpeg"), probe=lambda path: path.stat().st_size).run(job(batch.id), None, control)
    stopped = repo.get(batch.id)
    assert stopped.status == "cancelled"
    assert [item.status for item in stopped.items] == ["completed", "queued", "queued"]
