from __future__ import annotations

import importlib
from pathlib import Path

from fastapi.testclient import TestClient


def test_health_reports_database_ready(unicode_data_dir: Path) -> None:
    config_module = importlib.import_module("blueframe.config")
    app_module = importlib.import_module("blueframe.app")
    database_path = unicode_data_dir / "health.db"
    settings = config_module.Settings(
        data_dir=unicode_data_dir,
        database_url=f"sqlite:///{database_path.as_posix()}",
    )

    with TestClient(app_module.create_app(settings)) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "ok"}
