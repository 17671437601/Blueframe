from pathlib import Path
from types import SimpleNamespace
from datetime import UTC, datetime

from fastapi.testclient import TestClient

from blueframe.app import create_app
from blueframe.auth.service import StandaloneAccountService
from blueframe.drama.repository import StoryAnalysisRepository
from blueframe.jobs.repository import JobRepository
from blueframe.projects.models import ProjectType
from blueframe.projects.repository import ProjectRepository
from blueframe.providers.volcengine.config_service import ArkConfigStatus
from blueframe.api.routes.analysis import _create_initial_plan
from blueframe.drama.models import EdlCandidate, StoryAnalysis, StoryAnalysisVersion


HEADERS = {"X-BlueFrame-Session": "a" * 64}


class ConfigState:
    def __init__(self, configured: bool) -> None:
        self.configured = configured

    def status(self):
        return ArkConfigStatus(configured=self.configured, model="ep-test" if self.configured else None)


def client(session_factory, tmp_path: Path, configured=True):
    projects = ProjectRepository(session_factory)
    project = projects.create(
        name="Analyze", project_type=ProjectType.DRAMA, root_path=tmp_path,
        output_relative_path="out", config={}, idempotency_key="api-analysis-project",
    )
    app = create_app(
        session_token="a" * 64,
        job_repository=JobRepository(session_factory),
        account_service=StandaloneAccountService(),
        project_repository=projects,
        analysis_repository=StoryAnalysisRepository(session_factory),
        provider_config_service=ConfigState(configured),
    )
    return TestClient(app), project


def test_analysis_requires_explicit_consent_and_provider(migrated_session_factory, tmp_path) -> None:
    api, project = client(migrated_session_factory, tmp_path)
    with api:
        denied = api.post(
            f"/api/v1/projects/{project.id}/analyze", headers=HEADERS,
            json={"consent_to_send_transcript": False, "idempotency_key": "one"},
        )
    assert denied.status_code == 400
    assert denied.json()["detail"]["code"] == "transcript_consent_required"

    api, project = client(migrated_session_factory, tmp_path, configured=False)
    with api:
        missing = api.post(
            f"/api/v1/projects/{project.id}/analyze", headers=HEADERS,
            json={"consent_to_send_transcript": True, "idempotency_key": "two"},
        )
    assert missing.status_code == 409
    assert missing.json()["detail"]["code"] == "provider_not_configured"


def test_analysis_can_be_queued_listed_and_retried(migrated_session_factory, tmp_path) -> None:
    api, project = client(migrated_session_factory, tmp_path)
    with api:
        first = api.post(
            f"/api/v1/projects/{project.id}/analyze", headers=HEADERS,
            json={"consent_to_send_transcript": True, "idempotency_key": "run-one"},
        )
        retry = api.post(
            f"/api/v1/projects/{project.id}/analyze", headers=HEADERS,
            json={"consent_to_send_transcript": True, "idempotency_key": "run-two"},
        )
        listed = api.get(f"/api/v1/projects/{project.id}/analyses", headers=HEADERS)

    assert first.status_code == retry.status_code == 202
    assert first.json()["id"] != retry.json()["id"]
    assert listed.json() == []


def test_acceptance_maps_global_ai_ranges_across_source_boundaries() -> None:
    saved = []
    plans = SimpleNamespace(save=lambda project, draft, idempotency_key: saved.append((project, draft, idempotency_key)))
    version = StoryAnalysisVersion(
        id="analysis-1", project_id="project-1", version=1, prompt_version="v1",
        provider="fixture", model="m", accepted=True, created_at=datetime.now(UTC),
        analysis=StoryAnalysis(
            episode_summary="summary", media_duration_ms=10_000,
            edit_candidates=(EdlCandidate(title="跨集高光", rationale="反转", segments=((4000, 6000),)),),
        ),
    )
    sources = [
        SimpleNamespace(id="s1", media_info={"duration_ms": 5000}),
        SimpleNamespace(id="s2", media_info={"duration_ms": 5000}),
    ]
    _create_initial_plan("project-1", version, sources, plans)
    segments = saved[0][1].segments
    assert [(item.source_id, item.source_start_ms, item.source_end_ms) for item in segments] == [
        ("s1", 4000, 5000), ("s2", 0, 1000),
    ]
