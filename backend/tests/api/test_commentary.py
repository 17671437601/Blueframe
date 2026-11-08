from pathlib import Path

from fastapi.testclient import TestClient

from blueframe.app import create_app
from blueframe.auth.service import StandaloneAccountService
from blueframe.commentary.repository import CommentaryRepository
from blueframe.jobs.repository import JobRepository
from blueframe.projects.models import ProjectType
from blueframe.projects.repository import ProjectRepository
from blueframe.providers.volcengine.config_service import ArkConfigStatus


HEADERS = {"X-BlueFrame-Session": "a" * 64}


class ConfigState:
    def status(self): return ArkConfigStatus(configured=True, model="ep-test")


class TtsState:
    def status(self): return type("Status", (), {"configured": True})()


def test_commentary_api_queues_generation_and_versions_manual_edits(migrated_session_factory, tmp_path: Path) -> None:
    projects = ProjectRepository(migrated_session_factory)
    project = projects.create(
        name="Movie", project_type=ProjectType.MOVIE, root_path=tmp_path,
        output_relative_path="out", config={}, idempotency_key="commentary-api-project",
    )
    scripts = CommentaryRepository(migrated_session_factory)
    app = create_app(
        session_token="a" * 64, project_repository=projects,
        job_repository=JobRepository(migrated_session_factory), account_service=StandaloneAccountService(),
        commentary_repository=scripts, provider_config_service=ConfigState(), tts_config_service=TtsState(),
    )
    with TestClient(app) as client:
        queued = client.post(f"/api/v1/projects/{project.id}/commentary/generate", headers=HEADERS, json={
            "voice": "voice-a", "consent_to_send_transcript": True, "idempotency_key": "generate-one",
        })
        base = scripts.save(
            project_id=project.id, title="初稿", voice="voice-a", prompt_version="fixture",
            provider="fixture", model="m", sentences=(),
        )
        edited = client.put(f"/api/v1/projects/{project.id}/commentary/{base.id}", headers=HEADERS, json={
            "title": "人工稿", "voice": "voice-b",
            "sentences": [{"text": "这是人工补写的开场。", "citations": [], "manual": True}],
        })
        voiced = client.post(f"/api/v1/projects/{project.id}/commentary/{edited.json()['id']}/voice", headers=HEADERS, json={"idempotency_key": "voice-one"})
        listed = client.get(f"/api/v1/projects/{project.id}/commentary", headers=HEADERS)

    assert queued.status_code == 202
    assert queued.json()["job_type"] == "generate_commentary"
    assert edited.status_code == 200
    assert voiced.status_code == 202
    assert voiced.json()["job_type"] == "synthesize_commentary"
    assert edited.json()["version"] == 2
    assert [item["version"] for item in listed.json()] == [2, 1]


def test_commentary_generation_requires_transcript_consent(migrated_session_factory, tmp_path: Path) -> None:
    projects = ProjectRepository(migrated_session_factory)
    project = projects.create(name="Movie", project_type=ProjectType.MOVIE, root_path=tmp_path, output_relative_path="out", config={}, idempotency_key="consent-project")
    app = create_app(
        session_token="a" * 64, project_repository=projects,
        job_repository=JobRepository(migrated_session_factory), account_service=StandaloneAccountService(),
        commentary_repository=CommentaryRepository(migrated_session_factory), provider_config_service=ConfigState(),
    )
    with TestClient(app) as client:
        denied = client.post(f"/api/v1/projects/{project.id}/commentary/generate", headers=HEADERS, json={
            "voice": "voice-a", "consent_to_send_transcript": False, "idempotency_key": "denied",
        })
    assert denied.status_code == 400
