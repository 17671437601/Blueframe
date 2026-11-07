from datetime import datetime

from blueframe.jobs.repository import JobRepository


def recover_expired_leases(
    repository: JobRepository, *, now: datetime, max_attempts: int
) -> int:
    return repository.recover_expired(now=now, max_attempts=max_attempts)
