from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from fastapi.testclient import TestClient

from blueframe.app import create_app
from blueframe.jobs.repository import JobRepository
from blueframe.media.probe import MediaInfo
from blueframe.projects.repository import ProjectRepository
from blueframe.security.project_paths import ProjectPathRegistry
from tests.api.test_security import StaticAccountService


TOKEN = "p" * 64
HEADERS = {"X-BlueFrame-Session": TOKEN}
NOW = datetime(2026, 11, 8, 11, 0, tzinfo=UTC)


def media_info() -> MediaInfo:
    return MediaInfo(
        duration_ms=10000, size_bytes=5, format_name="mp4", width=1920,
        height=1080, rotation=0, frame_rate=25, video_codec="h264",
        has_audio=True, audio_codec="aac", audio_sample_rate=48000,
        audio_channels=2,
    )


def build_client(session_factory, root: Path, *, mode="online", bridge_secret=None):
    registry = ProjectPathRegistry()
    root_id = registry.register(root)
    app = create_app(
        session_token=TOKEN,
        job_repository=JobRepository(session_factory, clock=lambda: NOW),
        account_service=StaticAccountService(mode),
        project_repository=ProjectRepository(session_factory, clock=lambda: NOW),
        project_path_registry=registry,
        media_probe=lambda _path: media_info(),
        bridge_secret=bridge_secret,
    )
    return TestClient(app), root_id


def test_internal_bridge_registers_root_without_echoing_absolute_path(
    migrated_session_factory, tmp_path: Path
) -> None:
    root = tmp_path / "受信目录"
    root.mkdir()
    client, _ = build_client(
        migrated_session_factory, root, bridge_secret="bridge-secret"
    )
    with client:
        assert client.post(
            "/internal/project-roots", json={"root_path": str(root)}
        ).status_code == 401
        response = client.post(
            "/internal/project-roots",
            headers={"X-BlueFrame-Bridge": "bridge-secret"},
            json={"root_path": str(root)},
        )
    assert response.status_code == 201
    assert "root_id" in response.json()
    assert str(root) not in response.text


def test_project_routes_create_import_probe_list_and_queue_transcription(
    migrated_session_factory, tmp_path: Path
) -> None:
    root = tmp_path / "中文 项目"
    source_dir = root / "第一集"
    source_dir.mkdir(parents=True)
    (source_dir / "正片.mp4").write_bytes(b"video")
    client, root_id = build_client(migrated_session_factory, root)

    with client:
        assert client.get("/api/v1/projects").status_code == 401
        created = client.post(
            "/api/v1/projects",
            headers=HEADERS,
            json={
                "name": "都市悬疑", "project_type": "drama", "root_id": root_id,
                "output_relative_path": "交付", "config": {"target_seconds": 480},
                "idempotency_key": "api-project-1",
            },
        )
        assert created.status_code == 201
        body = created.json()
        assert "root_path" not in body and str(root) not in created.text
        project_id = body["id"]

        imported = client.post(
            f"/api/v1/projects/{project_id}/sources",
            headers=HEADERS,
            json={"relative_paths": ["第一集/正片.mp4"]},
        )
        assert imported.status_code == 201
        assert imported.json()[0]["media_info"]["duration_ms"] == 10000
        assert client.get("/api/v1/projects", headers=HEADERS).json()[0]["id"] == project_id
        assert client.get(f"/api/v1/projects/{project_id}", headers=HEADERS).status_code == 200

        queued = client.post(
            f"/api/v1/projects/{project_id}/transcribe", headers=HEADERS
        )
        assert queued.status_code == 202
        assert queued.json()["job_type"] == "transcribe_project"


def test_project_routes_block_escape_missing_and_readonly(
    migrated_session_factory, tmp_path: Path
) -> None:
    root = tmp_path / "root"
    root.mkdir()
    client, root_id = build_client(migrated_session_factory, root)
    with client:
        created = client.post(
            "/api/v1/projects", headers=HEADERS,
            json={"name": "项目", "project_type": "drama", "root_id": root_id,
                  "output_relative_path": "out", "config": {}, "idempotency_key": "p"},
        )
        project_id = created.json()["id"]
        escaped = client.post(
            f"/api/v1/projects/{project_id}/sources", headers=HEADERS,
            json={"relative_paths": ["../outside.mp4"]},
        )
        assert escaped.status_code == 400
        assert client.get("/api/v1/projects/missing", headers=HEADERS).status_code == 404

    readonly, readonly_root = build_client(migrated_session_factory, root, mode="readonly")
    with readonly:
        denied = readonly.post(
            "/api/v1/projects", headers=HEADERS,
            json={"name": "blocked", "project_type": "drama", "root_id": readonly_root,
                  "output_relative_path": "out", "config": {}, "idempotency_key": "blocked"},
        )
        assert denied.status_code == 403
        assert readonly.get("/api/v1/projects", headers=HEADERS).status_code == 200
