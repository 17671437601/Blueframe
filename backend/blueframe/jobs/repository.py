from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from typing import Any, Callable
from uuid import uuid4

from sqlalchemy import text
from sqlalchemy.orm import Session, sessionmaker

from blueframe.jobs.models import Job, JobStatus
from blueframe.jobs.state_machine import ensure_transition


class JobRepository:
    def __init__(
        self,
        session_factory: sessionmaker[Session],
        *,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self._session_factory = session_factory
        self._clock = clock

    def create(
        self,
        job_type: str,
        payload: dict[str, Any],
        idempotency_key: str,
        *,
        priority: int = 0,
    ) -> Job:
        now = self._clock()
        with self._session_factory.begin() as session:
            existing = session.execute(
                text("SELECT * FROM jobs WHERE job_type=:type AND idempotency_key=:key"),
                {"type": job_type, "key": idempotency_key},
            ).mappings().first()
            if existing is not None:
                return _job(existing)
            job_id = str(uuid4())
            session.execute(
                text(
                    """INSERT INTO jobs
                    (id, job_type, payload, status, priority, progress, attempts,
                     idempotency_key, created_at, updated_at)
                    VALUES (:id, :type, :payload, 'queued', :priority, 0, 0,
                            :key, :now, :now)"""
                ),
                {
                    "id": job_id,
                    "type": job_type,
                    "payload": json.dumps(payload, ensure_ascii=False),
                    "priority": priority,
                    "key": idempotency_key,
                    "now": now.isoformat(),
                },
            )
            self._event(session, job_id, None, JobStatus.QUEUED, now)
            return self._get(session, job_id)

    def claim_next(
        self,
        worker_id: str,
        *,
        lease_seconds: int,
        job_types: tuple[str, ...] | None = None,
    ) -> Job | None:
        if job_types == ():
            return None
        now = self._clock()
        expiry = now + timedelta(seconds=lease_seconds)
        type_filter = ""
        type_parameters: dict[str, str] = {}
        if job_types is not None:
            placeholders = []
            for index, job_type in enumerate(job_types):
                name = f"type_{index}"
                placeholders.append(f":{name}")
                type_parameters[name] = job_type
            type_filter = f" AND job_type IN ({','.join(placeholders)})"
        with self._session_factory.begin() as session:
            row = session.execute(
                text(
                    """UPDATE jobs SET status='running', lease_owner=:owner,
                      lease_expires_at=:expiry, attempts=attempts+1, updated_at=:now
                      WHERE id=(SELECT id FROM jobs WHERE status='queued'
                                """ + type_filter + """
                                ORDER BY priority DESC, created_at ASC LIMIT 1)
                        AND status='queued' RETURNING *"""
                ),
                {
                    "owner": worker_id,
                    "expiry": expiry.isoformat(),
                    "now": now.isoformat(),
                    **type_parameters,
                },
            ).mappings().first()
            if row is None:
                return None
            self._event(session, row.id, JobStatus.QUEUED, JobStatus.RUNNING, now)
            return _job(row)

    def get(self, job_id: str) -> Job | None:
        with self._session_factory() as session:
            row = session.execute(
                text("SELECT * FROM jobs WHERE id=:id"), {"id": job_id}
            ).mappings().first()
            return None if row is None else _job(row)

    def list(self) -> list[Job]:
        with self._session_factory() as session:
            rows = session.execute(
                text("SELECT * FROM jobs ORDER BY created_at DESC")
            ).mappings().all()
            return [_job(row) for row in rows]

    def request_pause(self, job_id: str) -> Job:
        return self._transition(job_id, JobStatus.PAUSING)

    def mark_paused(
        self, job_id: str, checkpoint: dict[str, Any], *, worker_id: str
    ) -> Job:
        return self._transition(
            job_id,
            JobStatus.PAUSED,
            owner=worker_id,
            values={"checkpoint": json.dumps(checkpoint), "lease_owner": None, "lease_expires_at": None},
        )

    def resume(self, job_id: str) -> Job:
        return self._transition(job_id, JobStatus.QUEUED)

    def cancel(self, job_id: str) -> Job:
        job = self.get(job_id)
        if job is None:
            raise KeyError(job_id)
        target = (
            JobStatus.CANCELLED
            if job.status is JobStatus.QUEUED
            else JobStatus.CANCELLING
        )
        return self._transition(job_id, target)

    def heartbeat(self, job_id: str, worker_id: str, *, lease_seconds: int) -> Job:
        now = self._clock()
        expiry = now + timedelta(seconds=lease_seconds)
        with self._session_factory.begin() as session:
            current = self._get(session, job_id)
            self._require_owner(current, worker_id)
            result = session.execute(
                text(
                    "UPDATE jobs SET lease_expires_at=:expiry, updated_at=:now "
                    "WHERE id=:id AND lease_owner=:owner"
                ),
                {"expiry": expiry.isoformat(), "now": now.isoformat(), "id": job_id, "owner": worker_id},
            )
            if result.rowcount != 1:
                raise PermissionError("worker is not the lease owner")
            self._event(session, job_id, current.status, current.status, now)
            return self._get(session, job_id)

    def update_progress(
        self, job_id: str, worker_id: str, progress: float, stage: str | None
    ) -> Job:
        now = self._clock()
        bounded = max(0.0, min(100.0, progress))
        with self._session_factory.begin() as session:
            current = self._get(session, job_id)
            self._require_owner(current, worker_id)
            session.execute(
                text(
                    "UPDATE jobs SET progress=:progress, stage=:stage, updated_at=:now "
                    "WHERE id=:id AND lease_owner=:owner"
                ),
                {
                    "progress": bounded,
                    "stage": stage,
                    "now": now.isoformat(),
                    "id": job_id,
                    "owner": worker_id,
                },
            )
            return self._get(session, job_id)

    def save_checkpoint(
        self, job_id: str, worker_id: str, checkpoint: dict[str, Any]
    ) -> Job:
        now = self._clock()
        with self._session_factory.begin() as session:
            current = self._get(session, job_id)
            self._require_owner(current, worker_id)
            session.execute(
                text("UPDATE jobs SET checkpoint=:checkpoint, updated_at=:now WHERE id=:id"),
                {
                    "checkpoint": json.dumps(checkpoint, ensure_ascii=False),
                    "now": now.isoformat(),
                    "id": job_id,
                },
            )
            return self._get(session, job_id)

    def complete(self, job_id: str, worker_id: str) -> Job:
        return self._transition(
            job_id,
            JobStatus.COMPLETED,
            owner=worker_id,
            values={"progress": 100, "lease_owner": None, "lease_expires_at": None},
        )

    def mark_cancelled(self, job_id: str, worker_id: str) -> Job:
        return self._transition(
            job_id,
            JobStatus.CANCELLED,
            owner=worker_id,
            values={"lease_owner": None, "lease_expires_at": None},
        )

    def fail(
        self,
        job_id: str,
        error_code: str,
        summary: str,
        *,
        worker_id: str | None = None,
    ) -> Job:
        return self._transition(
            job_id,
            JobStatus.FAILED,
            owner=worker_id,
            values={
                "error_code": error_code,
                "error_summary": summary,
                "lease_owner": None,
                "lease_expires_at": None,
            },
        )

    def recover_expired(self, *, now: datetime, max_attempts: int) -> int:
        with self._session_factory.begin() as session:
            rows = session.execute(
                text(
                    """SELECT * FROM jobs
                    WHERE status IN ('running','pausing','cancelling')
                      AND lease_expires_at IS NOT NULL
                      AND lease_expires_at < :now"""
                ),
                {"now": now.isoformat()},
            ).mappings().all()
            for row in rows:
                job = _job(row)
                ensure_transition(job.status, JobStatus.INTERRUPTED)
                session.execute(
                    text(
                        "UPDATE jobs SET status='interrupted', lease_owner=NULL, "
                        "lease_expires_at=NULL, updated_at=:now WHERE id=:id"
                    ),
                    {"now": now.isoformat(), "id": job.id},
                )
                self._event(session, job.id, job.status, JobStatus.INTERRUPTED, now)
                if job.attempts >= max_attempts:
                    target = JobStatus.FAILED
                    session.execute(
                        text(
                            "UPDATE jobs SET status='failed', error_code='lease_exhausted', "
                            "error_summary='worker lease retry limit exhausted', updated_at=:now "
                            "WHERE id=:id"
                        ),
                        {"now": now.isoformat(), "id": job.id},
                    )
                else:
                    target = JobStatus.QUEUED
                    session.execute(
                        text("UPDATE jobs SET status='queued', updated_at=:now WHERE id=:id"),
                        {"now": now.isoformat(), "id": job.id},
                    )
                self._event(session, job.id, JobStatus.INTERRUPTED, target, now)
            return len(rows)

    def _transition(
        self,
        job_id: str,
        target: JobStatus,
        *,
        owner: str | None = None,
        values: dict[str, Any] | None = None,
    ) -> Job:
        now = self._clock()
        with self._session_factory.begin() as session:
            current = self._get(session, job_id)
            if owner is not None:
                self._require_owner(current, owner)
            ensure_transition(current.status, target)
            assignments = {"status": target.value, "updated_at": now.isoformat(), **(values or {})}
            clause = ", ".join(f"{key}=:{key}" for key in assignments)
            session.execute(
                text(f"UPDATE jobs SET {clause} WHERE id=:id"),
                {**assignments, "id": job_id},
            )
            self._event(session, job_id, current.status, target, now)
            return self._get(session, job_id)

    def _get(self, session: Session, job_id: str) -> Job:
        row = session.execute(
            text("SELECT * FROM jobs WHERE id=:id"), {"id": job_id}
        ).mappings().first()
        if row is None:
            raise KeyError(job_id)
        return _job(row)

    @staticmethod
    def _require_owner(job: Job, worker_id: str) -> None:
        if job.lease_owner != worker_id:
            raise PermissionError("worker is not the lease owner")

    @staticmethod
    def _event(
        session: Session,
        job_id: str,
        source: JobStatus | None,
        target: JobStatus,
        now: datetime,
    ) -> None:
        session.execute(
            text(
                "INSERT INTO job_events (job_id, from_status, to_status, data, created_at) "
                "VALUES (:job_id, :source, :target, '{}', :created_at)"
            ),
            {
                "job_id": job_id,
                "source": None if source is None else source.value,
                "target": target.value,
                "created_at": now.isoformat(),
            },
        )


def _job(row: Any) -> Job:
    return Job(
        id=row.id,
        job_type=row.job_type,
        payload=json.loads(row.payload),
        status=JobStatus(row.status),
        priority=row.priority,
        progress=row.progress,
        stage=row.stage,
        attempts=row.attempts,
        lease_owner=row.lease_owner,
        lease_expires_at=_datetime(row.lease_expires_at),
        checkpoint=None if row.checkpoint is None else json.loads(row.checkpoint),
        idempotency_key=row.idempotency_key,
        error_code=row.error_code,
        error_summary=row.error_summary,
        created_at=_datetime(row.created_at),
        updated_at=_datetime(row.updated_at),
    )


def _datetime(value: datetime | str | None) -> datetime | None:
    if value is None or isinstance(value, datetime):
        return value
    return datetime.fromisoformat(value)
