from __future__ import annotations

import importlib
from datetime import UTC, datetime, timedelta


def test_expired_lease_records_interruption_requeues_and_rejects_stale_owner(
    migrated_session_factory,
) -> None:
    repository_type = importlib.import_module("blueframe.jobs.repository").JobRepository
    recovery = importlib.import_module("blueframe.workers.recovery")
    started = datetime(2026, 11, 7, tzinfo=UTC)
    repository = repository_type(migrated_session_factory, clock=lambda: started)
    job = repository.create("render", {}, "recover")
    repository.claim_next("old-worker", lease_seconds=30)

    count = recovery.recover_expired_leases(
        repository, now=started + timedelta(seconds=31), max_attempts=3
    )

    recovered = repository.get(job.id)
    assert count == 1
    assert recovered.status.value == "queued"
    assert recovered.attempts == 1
    try:
        repository.complete(job.id, "old-worker")
    except (PermissionError, ValueError):
        pass
    else:
        raise AssertionError("expired owner must not complete recovered job")


def test_expired_lease_exhaustion_fails_job(migrated_session_factory) -> None:
    repository_type = importlib.import_module("blueframe.jobs.repository").JobRepository
    recovery = importlib.import_module("blueframe.workers.recovery")
    started = datetime(2026, 11, 7, tzinfo=UTC)
    repository = repository_type(migrated_session_factory, clock=lambda: started)
    job = repository.create("render", {}, "exhaust")
    repository.claim_next("worker", lease_seconds=1)

    recovery.recover_expired_leases(
        repository, now=started + timedelta(seconds=2), max_attempts=1
    )

    failed = repository.get(job.id)
    assert failed.status.value == "failed"
    assert failed.error_code == "lease_exhausted"
