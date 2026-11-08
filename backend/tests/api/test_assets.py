from pathlib import Path

from fastapi.testclient import TestClient

from blueframe.app import create_app
from blueframe.assets.repository import AssetRepository
from blueframe.assets.scanner import AssetScanner
from blueframe.security.project_paths import ProjectPathRegistry


HEADERS = {"X-BlueFrame-Session": "a" * 64}


def test_asset_api_imports_with_provenance_without_leaking_absolute_path(migrated_session_factory, tmp_path: Path) -> None:
    source = tmp_path / "海报.png"; source.write_bytes(b"\x89PNG\r\n\x1a\nfixture")
    roots = ProjectPathRegistry(); root_id = roots.register(tmp_path)
    app = create_app(
        session_token="a" * 64, project_path_registry=roots,
        asset_repository=AssetRepository(migrated_session_factory), asset_scanner=AssetScanner(),
    )
    with TestClient(app) as client:
        imported = client.post("/api/v1/assets", headers=HEADERS, json={
            "root_id": root_id, "relative_paths": ["海报.png"], "origin": "自有素材",
            "license_name": "版权所有者授权", "ownership": "linked",
        })
        listed = client.get("/api/v1/assets", headers=HEADERS)
    assert imported.status_code == 201
    assert listed.json()[0]["filename"] == "海报.png"
    assert listed.json()[0]["license_name"] == "版权所有者授权"
    assert str(tmp_path) not in listed.text
