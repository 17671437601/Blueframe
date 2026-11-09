import sqlite3
from pathlib import Path

from fastapi.testclient import TestClient

from blueframe.app import create_app
from blueframe.legacy.importer import LegacyImporter
from blueframe.security.project_paths import ProjectPathRegistry


HEADERS = {"X-BlueFrame-Session": "a" * 64}


def test_legacy_import_api_requires_preview_hash_and_explicit_confirmation(migrated_session_factory, tmp_path: Path) -> None:
    database = tmp_path / "video.db"
    connection = sqlite3.connect(database)
    connection.execute("CREATE TABLE drama_project (id text,name text,source_path text,duration real,width integer,height integer,status text,settings text)")
    connection.execute("INSERT INTO drama_project VALUES ('old','旧项目','',10,1920,1080,'done','{}')")
    connection.commit(); connection.close()
    roots = ProjectPathRegistry(); root_id = roots.register(tmp_path)
    app = create_app(
        session_token="a" * 64, project_path_registry=roots,
        legacy_importer=LegacyImporter(migrated_session_factory),
    )

    with TestClient(app) as client:
        preview = client.post("/api/v1/legacy-import/preview", headers=HEADERS, json={"root_id": root_id, "relative_path": "video.db"})
        denied = client.post("/api/v1/legacy-import/confirm", headers=HEADERS, json={
            "root_id": root_id, "relative_path": "video.db",
            "expected_source_hash": preview.json()["source_hash"], "confirmed": False,
        })
        imported = client.post("/api/v1/legacy-import/confirm", headers=HEADERS, json={
            "root_id": root_id, "relative_path": "video.db",
            "expected_source_hash": preview.json()["source_hash"], "confirmed": True,
        })

    assert preview.status_code == 200 and preview.json()["projects"][0]["name"] == "旧项目"
    assert denied.status_code == 400
    assert imported.status_code == 200 and imported.json()["imported"] == 1
    assert str(tmp_path) not in preview.text + imported.text
