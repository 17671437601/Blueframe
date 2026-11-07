from __future__ import annotations

import importlib
from datetime import UTC, datetime


def _runtime(session_factory, handler):
    repository_module = importlib.import_module("blueframe.jobs.repository")
    runner_module = importlib.import_module("blueframe.workers.runner")
    now = datetime(2026, 11, 7, tzinfo=UTC)
    repository = repository_module.JobRepository(session_factory, clock=lambda: now)
    runner = runner_module.WorkerRunner(
        repository, {"render": handler}, worker_id="worker-1", lease_seconds=60
    )
    return repository, runner


def test_runner_heartbeats_clamps_progress_and_completes(migrated_session_factory) -> None:
    class Handler:
        calls = 0

        def run(self, job, checkpoint, control):
            self.calls += 1
            control.heartbeat()
            control.progress(150, "rendering")
            return importlib.import_module("blueframe.workers.protocol").JobResult()

    handler = Handler()
    repository, runner = _runtime(migrated_session_factory, handler)
    created = repository.create("render", {}, "render-once")

    assert runner.run_once() is True
    completed = repository.get(created.id)
    assert completed is not None and completed.status.value == "completed"
    assert completed.progress == 100
    assert completed.stage == "rendering"
    repository.create("render", {"changed": True}, "render-once")
    assert runner.run_once() is False
    assert handler.calls == 1


def test_runner_cooperatively_pauses_after_checkpoint(migrated_session_factory) -> None:
    holder = {}

    class Handler:
        def run(self, job, checkpoint, control):
            holder["repository"].request_pause(job.id)
            control.checkpoint({"segment": 4})
            assert control.pause_requested is True
            return importlib.import_module("blueframe.workers.protocol").JobResult()

    repository, runner = _runtime(migrated_session_factory, Handler())
    holder["repository"] = repository
    created = repository.create("render", {}, "pause")

    runner.run_once()

    paused = repository.get(created.id)
    assert paused is not None and paused.status.value == "paused"
    assert paused.checkpoint == {"segment": 4}


def test_runner_cooperatively_cancels_and_sanitizes_failures(
    migrated_session_factory,
) -> None:
    holder = {}

    class CancelHandler:
        def run(self, job, checkpoint, control):
            holder["repository"].cancel(job.id)
            assert control.cancel_requested is True
            return importlib.import_module("blueframe.workers.protocol").JobResult()

    repository, runner = _runtime(migrated_session_factory, CancelHandler())
    holder["repository"] = repository
    cancel_job = repository.create("render", {}, "cancel")
    runner.run_once()
    assert repository.get(cancel_job.id).status.value == "cancelled"

    class FailingHandler:
        def run(self, job, checkpoint, control):
            raise RuntimeError("Authorization: secret-value\nprovider failed")

    repository.create("render", {}, "failure")
    failing_runner = importlib.import_module("blueframe.workers.runner").WorkerRunner(
        repository, {"render": FailingHandler()}, worker_id="worker-2", lease_seconds=60
    )
    failing_runner.run_once()
    failed = repository.get(repository.create("render", {}, "failure").id)
    assert failed.status.value == "failed"
    assert "secret-value" not in failed.error_summary
    assert len(failed.error_summary) <= 500
