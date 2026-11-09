from __future__ import annotations

import os
import subprocess
import sys
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

from blueframe.jobs.repository import JobRepository
from blueframe.workers.protocol import JobResult
from blueframe.workers.recovery import recover_expired_leases
from blueframe.workers.runner import WorkerRunner

ROOT = Path(__file__).resolve().parents[2]
HELPER = Path(__file__).with_name("_killed_worker.py")


class CompleteHandler:
    def __init__(self) -> None:
        self.checkpoints: list[dict | None] = []

    def run(self, job, checkpoint, control) -> JobResult:
        self.checkpoints.append(checkpoint)
        control.progress(100, "restarted")
        return JobResult()


def test_killed_worker_lease_is_recovered_and_job_completes_after_restart(
    migrated_session_factory, tmp_path: Path,
) -> None:
    repository = JobRepository(migrated_session_factory)
    job = repository.create("render", {"project_id": "project-1"}, "kill-restart")
    marker = tmp_path / "claimed.txt"
    environment = os.environ.copy()
    environment["PYTHONPATH"] = str(ROOT)
    process = subprocess.Popen(
        [sys.executable, str(HELPER), str(marker)],
        cwd=str(ROOT), env=environment,
        stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True,
    )
    try:
        deadline = time.monotonic() + 20
        while time.monotonic() < deadline and not marker.exists():
            if process.poll() is not None:
                break
            time.sleep(0.05)
        assert marker.exists(), "helper worker never claimed the job"
        assert process.poll() is None, "helper worker exited before it could be killed"
    finally:
        process.kill()
        process.wait(timeout=10)

    killed = repository.get(job.id)
    assert killed is not None
    assert killed.status.value == "running"
    assert killed.lease_owner == "killed-worker"

    now = datetime.now(UTC) + timedelta(seconds=120)
    recovered = recover_expired_leases(
        JobRepository(migrated_session_factory, clock=lambda: now),
        now=now, max_attempts=3,
    )
    assert recovered == 1
    assert repository.get(job.id).status.value == "queued"

    handler = CompleteHandler()
    runner = WorkerRunner(
        JobRepository(migrated_session_factory, clock=lambda: now),
        {"render": handler}, worker_id="new-worker", lease_seconds=30,
    )
    assert runner.run_once() is True

    completed = repository.get(job.id)
    assert completed.status.value == "completed"
    assert handler.checkpoints == [None]
