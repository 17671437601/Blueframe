from __future__ import annotations

import sqlite3
import time
from pathlib import Path

from blueframe.jobs.repository import JobRepository
from blueframe.legacy.importer import LegacyImporter
from blueframe.projects.repository import ProjectRepository


def legacy_database(path: Path, source: Path, count: int) -> None:
    connection = sqlite3.connect(path)
    connection.executescript("""
        CREATE TABLE drama_project (id text primary key,name text,source_path text,duration real,width integer,height integer,status text,settings text,created_at real,updated_at real);
        CREATE TABLE account (id integer,name text,cookie text);
    """)
    connection.executemany(
        "INSERT INTO drama_project VALUES (?,?,?,?,?,?,?,?,?,?)",
        [
            (
                f"old-{index}", f"短剧 {index}", str(source), 30.0, 1920, 1080,
                "completed", '{"target_duration":30}', float(index), float(index + 1),
            )
            for index in range(count)
        ],
    )
    connection.execute("INSERT INTO account VALUES (1,'user','secret-cookie')")
    connection.commit()
    connection.close()


def test_large_legacy_import_is_bounded_and_idempotent(
    migrated_session_factory, tmp_path: Path,
) -> None:
    source = tmp_path / "源.mp4"
    source.write_bytes(b"video")
    database = tmp_path / "video.db"
    legacy_database(database, source, 400)
    importer = LegacyImporter(migrated_session_factory)

    started = time.monotonic()
    report = importer.preview(database)
    first = importer.import_confirmed(
        database, expected_source_hash=report.source_hash, confirmed=True
    )
    second = importer.import_confirmed(
        database, expected_source_hash=report.source_hash, confirmed=True
    )
    elapsed = time.monotonic() - started

    assert len(report.projects) == 400
    assert first.imported == 400
    assert second.imported == 0 and second.skipped == 400
    assert len(ProjectRepository(migrated_session_factory).list()) == 400
    assert elapsed < 30


def test_large_job_queue_claims_everything_in_priority_then_age_order(
    migrated_session_factory,
) -> None:
    repository = JobRepository(migrated_session_factory)
    for index in range(500):
        repository.create("render", {"n": index}, f"bulk-{index}", priority=index % 3)

    claimed = []
    while (job := repository.claim_next("bulk-worker", lease_seconds=60)) is not None:
        claimed.append(job)

    assert len(claimed) == 500
    priorities = [job.priority for job in claimed]
    assert priorities == sorted(priorities, reverse=True)
