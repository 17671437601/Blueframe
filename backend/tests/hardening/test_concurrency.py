from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

from sqlalchemy import text

from blueframe.jobs.repository import JobRepository


def test_concurrent_idempotent_create_produces_exactly_one_job(
    migrated_session_factory,
) -> None:
    def create(_index: int):
        return JobRepository(migrated_session_factory).create("render", {}, "shared-key")

    with ThreadPoolExecutor(max_workers=8) as pool:
        jobs = list(pool.map(create, range(16)))

    assert len({job.id for job in jobs}) == 1
    with migrated_session_factory() as session:
        assert session.execute(text("SELECT COUNT(*) FROM jobs")).scalar_one() == 1


def test_concurrent_workers_never_double_claim_a_job(migrated_session_factory) -> None:
    repository = JobRepository(migrated_session_factory)
    created = {
        repository.create("render", {"n": index}, f"job-{index}").id
        for index in range(40)
    }

    def claim(worker_id: str) -> list[str]:
        claimed: list[str] = []
        worker_repository = JobRepository(migrated_session_factory)
        while True:
            job = worker_repository.claim_next(worker_id, lease_seconds=60)
            if job is None:
                return claimed
            claimed.append(job.id)

    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(claim, [f"worker-{index}" for index in range(4)]))

    claimed_ids = [job_id for group in results for job_id in group]
    assert len(claimed_ids) == len(set(claimed_ids)) == 40
    assert set(claimed_ids) == created
