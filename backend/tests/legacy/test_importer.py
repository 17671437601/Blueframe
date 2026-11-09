import sqlite3
from pathlib import Path

from blueframe.legacy.importer import LegacyImporter
from blueframe.projects.repository import ProjectRepository


def legacy_database(path: Path, source: Path) -> None:
    connection = sqlite3.connect(path)
    connection.executescript("""
        CREATE TABLE drama_project (id text primary key,name text,source_path text,duration real,width integer,height integer,status text,settings text,created_at real,updated_at real);
        CREATE TABLE account (id integer,name text,cookie text);
    """)
    connection.execute("INSERT INTO drama_project VALUES (?,?,?,?,?,?,?,?,?,?)", ("old-1", "旧短剧", str(source), 12.5, 1920, 1080, "completed", '{"target_duration":30}', 1, 2))
    connection.execute("INSERT INTO account VALUES (1,'user','secret-cookie')")
    connection.commit(); connection.close()


def test_preview_is_read_only_reports_exclusions_and_import_is_idempotent(migrated_session_factory, tmp_path: Path) -> None:
    source = tmp_path / "中文 源.mp4"; source.write_bytes(b"video")
    database = tmp_path / "video.db"; legacy_database(database, source)
    before = database.read_bytes()
    importer = LegacyImporter(migrated_session_factory)

    report = importer.preview(database)
    assert report.projects[0].name == "旧短剧"
    assert "account" in report.excluded_tables
    assert report.projects[0].source_available is True
    assert database.read_bytes() == before

    first = importer.import_confirmed(database, expected_source_hash=report.source_hash, confirmed=True)
    second = importer.import_confirmed(database, expected_source_hash=report.source_hash, confirmed=True)
    assert first.imported == 1
    assert second.imported == 0 and second.skipped == 1
    projects = ProjectRepository(migrated_session_factory).list()
    assert projects[0].name == "旧短剧"
    assert "secret-cookie" not in projects[0].config.model_dump_json()


def test_unknown_partial_schema_returns_warning_instead_of_guessing(migrated_session_factory, tmp_path: Path) -> None:
    database = tmp_path / "unknown.db"
    connection = sqlite3.connect(database); connection.execute("CREATE TABLE drama_project (id text,name text)"); connection.commit(); connection.close()
    report = LegacyImporter(migrated_session_factory).preview(database)
    assert report.projects == ()
    assert any("schema" in warning.lower() for warning in report.warnings)
