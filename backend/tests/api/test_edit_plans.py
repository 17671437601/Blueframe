from pathlib import Path

from fastapi.testclient import TestClient

from blueframe.app import create_app
from blueframe.auth.service import StandaloneAccountService
from blueframe.editing.repository import EditPlanRepository
from blueframe.jobs.repository import JobRepository
from blueframe.projects.models import ProjectType
from blueframe.projects.repository import ProjectRepository


HEADERS = {"X-BlueFrame-Session": "a" * 64}


def test_edit_plan_api_saves_versions_and_queues_render(migrated_session_factory, tmp_path: Path) -> None:
    projects = ProjectRepository(migrated_session_factory)
    project = projects.create(
        name="Editor", project_type=ProjectType.DRAMA, root_path=tmp_path,
        output_relative_path="out", config={}, idempotency_key="editor-api-project",
    )
    app = create_app(
        session_token="a" * 64, project_repository=projects,
        edit_plan_repository=EditPlanRepository(migrated_session_factory),
        job_repository=JobRepository(migrated_session_factory),
        account_service=StandaloneAccountService(),
    )
    payload = {
        "title": "高光方案", "kind": "highlight", "target_duration_ms": 3000,
        "segments": [{"source_id": "s1", "source_start_ms": 1000, "source_end_ms": 4000, "source_duration_ms": 10_000}],
        "idempotency_key": "plan-one",
    }
    with TestClient(app) as api:
        created = api.post(f"/api/v1/projects/{project.id}/edit-plans", headers=HEADERS, json=payload)
        listed = api.get(f"/api/v1/projects/{project.id}/edit-plans", headers=HEADERS)
        render = api.post(
            f"/api/v1/projects/{project.id}/edit-plans/{created.json()['id']}/render",
            headers=HEADERS,
            json={"script_id": "script-a"},
        )
    assert created.status_code == 201
    assert listed.json()[0]["duration_ms"] == 3000
    assert render.status_code == 202
    assert render.json()["job_type"] == "render_edit_plan"
    assert render.json()["payload"]["script_id"] == "script-a"


def test_edit_plan_api_rejects_cross_project_plan(migrated_session_factory, tmp_path: Path) -> None:
    projects = ProjectRepository(migrated_session_factory)
    first = projects.create(name="One", project_type=ProjectType.DRAMA, root_path=tmp_path,
        output_relative_path="out", config={}, idempotency_key="one")
    second = projects.create(name="Two", project_type=ProjectType.DRAMA, root_path=tmp_path,
        output_relative_path="out", config={}, idempotency_key="two")
    plans = EditPlanRepository(migrated_session_factory)
    from blueframe.editing.models import EditPlanDraft, EditSegment, PlanKind
    plan = plans.save(first.id, EditPlanDraft(title="x", kind=PlanKind.HIGHLIGHT,
        target_duration_ms=1000, segments=(EditSegment(source_id="s", source_start_ms=0,
        source_end_ms=1000, source_duration_ms=1000),)), idempotency_key="x")
    app = create_app(session_token="a" * 64, project_repository=projects,
        edit_plan_repository=plans, job_repository=JobRepository(migrated_session_factory),
        account_service=StandaloneAccountService())
    with TestClient(app) as api:
        response = api.post(f"/api/v1/projects/{second.id}/edit-plans/{plan.id}/render", headers=HEADERS)
    assert response.status_code == 404
