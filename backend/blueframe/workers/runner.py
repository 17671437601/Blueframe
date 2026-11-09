from __future__ import annotations

import re
import time
from typing import Any

from blueframe.jobs.models import JobStatus
from blueframe.jobs.repository import JobRepository
from blueframe.workers.protocol import JobHandler


class _Control:
    def __init__(
        self,
        repository: JobRepository,
        job_id: str,
        worker_id: str,
        lease_seconds: int,
        diagnostics=None,
    ) -> None:
        self.repository = repository
        self.job_id = job_id
        self.worker_id = worker_id
        self.lease_seconds = lease_seconds
        self.saved_checkpoint: dict[str, Any] | None = None
        self.diagnostics = diagnostics

    def heartbeat(self) -> None:
        self.repository.heartbeat(
            self.job_id, self.worker_id, lease_seconds=self.lease_seconds
        )

    def checkpoint(self, data: dict[str, Any]) -> None:
        self.saved_checkpoint = data
        self.repository.save_checkpoint(self.job_id, self.worker_id, data)

    def progress(self, value: float, stage: str | None = None) -> None:
        self.repository.update_progress(self.job_id, self.worker_id, value, stage)
        if self.diagnostics is not None and stage:
            self.diagnostics.record(category="worker", stage=stage, status="progress")

    @property
    def pause_requested(self) -> bool:
        job = self.repository.get(self.job_id)
        return job is not None and job.status is JobStatus.PAUSING

    @property
    def cancel_requested(self) -> bool:
        job = self.repository.get(self.job_id)
        return job is not None and job.status is JobStatus.CANCELLING


class WorkerRunner:
    def __init__(
        self,
        repository: JobRepository,
        handlers: dict[str, JobHandler],
        *,
        worker_id: str,
        lease_seconds: int,
        diagnostics=None,
        monotonic=time.monotonic,
    ) -> None:
        self.repository = repository
        self.handlers = handlers
        self.worker_id = worker_id
        self.lease_seconds = lease_seconds
        self.diagnostics = diagnostics
        self.monotonic = monotonic

    def run_once(self) -> bool:
        job = self.repository.claim_next(
            self.worker_id,
            lease_seconds=self.lease_seconds,
            job_types=tuple(self.handlers),
        )
        if job is None:
            return False
        started = self.monotonic()
        handler = self.handlers.get(job.job_type)
        if handler is None:
            self.repository.fail(
                job.id, "handler_missing", "no worker handler is registered", worker_id=self.worker_id
            )
            return True
        control = _Control(
            self.repository, job.id, self.worker_id, self.lease_seconds
            , self.diagnostics
        )
        try:
            handler.run(job, job.checkpoint, control)
            current = self.repository.get(job.id)
            if current is None:
                return True
            if current.status is JobStatus.PAUSING:
                self.repository.mark_paused(
                    job.id, control.saved_checkpoint or current.checkpoint or {}, worker_id=self.worker_id
                )
            elif current.status is JobStatus.CANCELLING:
                self.repository.mark_cancelled(job.id, self.worker_id)
            else:
                self.repository.complete(job.id, self.worker_id)
            self._record(job.job_type, current.stage or job.job_type, "completed", started)
        except Exception as error:
            current = self.repository.get(job.id)
            if current is not None and current.status not in {
                JobStatus.COMPLETED,
                JobStatus.CANCELLED,
                JobStatus.FAILED,
            }:
                self.repository.fail(
                    job.id,
                    "handler_error",
                    _sanitize_error(error),
                    worker_id=self.worker_id,
                )
                self._record(job.job_type, current.stage or job.job_type, "failed", started, "handler_error")
        return True

    def _record(self, job_type: str, stage: str, status: str, started: float, error_code: str | None = None) -> None:
        if self.diagnostics is None: return
        self.diagnostics.record(
            category="worker", stage=stage, status=status,
            duration_ms=max(0, round((self.monotonic() - started) * 1000)), error_code=error_code,
        )


def _sanitize_error(error: Exception) -> str:
    summary = " ".join(str(error).splitlines())
    summary = re.sub(
        r"(?i)(authorization|token|password|secret)\s*[:=]\s*\S+",
        r"\1: [redacted]",
        summary,
    )
    return summary[:500]
