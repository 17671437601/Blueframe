from pathlib import Path

from fastapi.testclient import TestClient

from blueframe.app import create_app
from blueframe.auth.credential_store import InMemoryCredentialStore
from blueframe.auth.service import StandaloneAccountService
from blueframe.live.repository import RecordingRepository
from blueframe.projects.models import ProjectType
from blueframe.projects.repository import ProjectRepository


HEADERS = {"X-BlueFrame-Session": "a" * 64}


class Engine:
    def __init__(self): self.started = []; self.stopped = []
    def start(self, session_id, root): self.started.append((session_id, root))
    def stop(self, session_id): self.stopped.append(session_id)
    def reconnect(self, session_id): self.started.append((session_id, "reconnect"))


def test_live_api_stores_url_as_external_credential_and_controls_session(migrated_session_factory, tmp_path: Path) -> None:
    projects = ProjectRepository(migrated_session_factory)
    project = projects.create(name="Live", project_type=ProjectType.LIVE, root_path=tmp_path, output_relative_path="out", config={}, idempotency_key="live-api")
    credentials, engine = InMemoryCredentialStore(), Engine()
    recordings = RecordingRepository(migrated_session_factory)
    app = create_app(
        session_token="a" * 64, project_repository=projects, recording_repository=recordings,
        live_credentials=credentials, live_engine=engine, account_service=StandaloneAccountService(),
    )
    secret_url = "https://stream.example/live.flv?token=super-secret"
    with TestClient(app) as client:
        created = client.post(f"/api/v1/projects/{project.id}/recordings", headers=HEADERS, json={
            "platform": "douyin", "display_name": "授权直播", "playback_url": secret_url,
            "authorization_confirmed": True,
        })
        listed = client.get(f"/api/v1/projects/{project.id}/recordings", headers=HEADERS)
        stopped = client.post(f"/api/v1/projects/{project.id}/recordings/{created.json()['id']}/stop", headers=HEADERS)
    assert created.status_code == 201 and stopped.status_code == 200
    assert engine.started and engine.stopped
    assert "super-secret" not in created.text + listed.text
    assert recordings.get(created.json()["id"]).source_reference != secret_url
