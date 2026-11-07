from __future__ import annotations

import importlib
from datetime import UTC, datetime, timedelta

from sqlalchemy import text


def _repository(session_factory, now: datetime):
    module = importlib.import_module("blueframe.jobs.repository")
    return module.JobRepository(session_factory, clock=lambda: now)


def test_create_is_idempotent_and_claims_priority_then_age(
    migrated_session_factory,
) -> None:
    now = datetime(2026, 11, 7, tzinfo=UTC)
    repository = _repository(migrated_session_factory, now)
    first = repository.create("render", {"source": "a"}, "same", priority=1)
    duplicate = repository.create("render", {"source": "changed"}, "same", priority=99)
    repository.create("render", {"source": "b"}, "older-low", priority=2)
    high = repository.create("render", {"source": "c"}, "high", priority=10)

    claimed = repository.claim_next("worker-1", lease_seconds=60)
    second_claim = repository.claim_next("worker-2", lease_seconds=60)

    assert duplicate.id == first.id
    assert duplicate.payload == {"source": "a"}
    assert claimed is not None and claimed.id == high.id
    assert claimed.lease_owner == "worker-1"
    assert second_claim is not None and second_claim.id != claimed.id


def test_pause_resume_heartbeat_complete_and_events_are_atomic(
    migrated_session_factory,
) -> None:
    now = datetime(2026, 11, 7, tzinfo=UTC)
    repository = _repository(migrated_session_factory, now)
    job = repository.create("asr", {}, "workflow")
    running = repository.claim_next("worker-1", lease_seconds=60)
    pausing = repository.request_pause(job.id)
    paused = repository.mark_paused(job.id, {"episode": 2}, worker_id="worker-1")
    queued = repository.resume(job.id)
    running_again = repository.claim_next("worker-2", lease_seconds=60)
    heartbeat = repository.heartbeat(job.id, "worker-2", lease_seconds=120)
    completed = repository.complete(job.id, "worker-2")

    assert running is not None and running.status.value == "running"
    assert pausing.status.value == "pausing"
    assert paused.status.value == "paused" and paused.checkpoint == {"episode": 2}
    assert queued.status.value == "queued"
    assert running_again is not None and running_again.status.value == "running"
    assert heartbeat.lease_expires_at == now + timedelta(seconds=120)
    assert completed.status.value == "completed"
    with migrated_session_factory() as session:
        event_statuses = session.execute(
            text("SELECT to_status FROM job_events WHERE job_id=:id ORDER BY created_at, id"),
            {"id": job.id},
        ).scalars().all()
    assert event_statuses == [
        "queued", "running", "pausing", "paused", "queued", "running", "running", "completed"
    ]


def test_stale_owner_cannot_complete_claimed_job(migrated_session_factory) -> None:
    now = datetime(2026, 11, 7, tzinfo=UTC)
    repository = _repository(migrated_session_factory, now)
    job = repository.create("render", {}, "owner-check")
    repository.claim_next("worker-1", lease_seconds=60)

    try:
        repository.complete(job.id, "worker-2")
    except PermissionError as error:
        assert "lease owner" in str(error)
    else:
        raise AssertionError("stale owner must not complete a job")


def test_cancel_queued_job_and_fail_owned_running_job(migrated_session_factory) -> None:
    now = datetime(2026, 11, 7, tzinfo=UTC)
    repository = _repository(migrated_session_factory, now)
    queued = repository.create("render", {}, "cancel-me")
    cancelled = repository.cancel(queued.id)
    running_job = repository.create("asr", {}, "fail-me", priority=10)
    repository.claim_next("worker-1", lease_seconds=60)

    failed = repository.fail(
        running_job.id, "model_error", "provider response invalid", worker_id="worker-1"
    )

    assert cancelled.status.value == "cancelled"
    assert failed.status.value == "failed"
    assert failed.error_code == "model_error"
    assert failed.error_summary == "provider response invalid"
    assert failed.lease_owner is None
