from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from blueframe.app import create_app
from blueframe.config import Settings


def test_file_origin_preflight_allows_desktop_session_header(tmp_path: Path) -> None:
    settings = Settings(data_dir=tmp_path, database_url=f"sqlite:///{(tmp_path / 'cors.db').as_posix()}")

    with TestClient(create_app(settings)) as client:
        for origin in ("null", "file://"):
            response = client.options(
                "/api/v1/system/status",
                headers={
                    "Origin": origin,
                    "Access-Control-Request-Method": "GET",
                    "Access-Control-Request-Headers": "x-blueframe-session",
                },
            )
            assert response.status_code == 200
            assert response.headers["access-control-allow-origin"] == origin
