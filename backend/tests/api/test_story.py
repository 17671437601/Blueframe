from pathlib import Path

from fastapi.testclient import TestClient

from blueframe.app import create_app
from blueframe.asr.repository import AsrRepository
from blueframe.auth.service import StandaloneAccountService
from blueframe.drama.models import ExplosionCandidate, StoryAnalysis
from blueframe.drama.repository import StoryAnalysisRepository
from blueframe.editing.repository import EditPlanRepository
from blueframe.jobs.repository import JobRepository
from blueframe.projects.models import ProjectType, SourceRegistration
from blueframe.projects.repository import ProjectRepository
from blueframe.story.repository import StoryBatchRepository

HEADERS = {"X-BlueFrame-Session": "a" * 64}


def _project(projects: ProjectRepository, tmp_path: Path, name: str, duration_ms: int = 600_000):
    project = projects.create(
        name=name, project_type=ProjectType.DRAMA, root_path=tmp_path,
        output_relative_path="out", config={}, idempotency_key=f"project-{name}",
    )
    source = tmp_path / f"{name}.mp4"
    source.write_bytes(b"episode")
    registered = projects.add_sources(
        project.id,
        [SourceRegistration(relative_path=f"{name}.mp4", size_bytes=7, modified_ns=1, content_fingerprint="f")],
    )[0]
    projects.update_media_info(
        registered.id, {"duration_ms": duration_ms, "has_audio": True, "rotation": 0}
    )
    return project, registered


def _app(session_factory):
    return create_app(
        session_token="a" * 64,
        project_repository=ProjectRepository(session_factory),
        analysis_repository=StoryAnalysisRepository(session_factory),
        story_batch_repository=StoryBatchRepository(session_factory),
        edit_plan_repository=EditPlanRepository(session_factory),
        job_repository=JobRepository(session_factory),
        account_service=StandaloneAccountService(),
        asr_repository=AsrRepository(session_factory),
    )


def test_story_api_creates_plans_and_queues_batch_job(
    migrated_session_factory, tmp_path: Path
) -> None:
    projects = ProjectRepository(migrated_session_factory)
    project, _source = _project(projects, tmp_path, "整剧")
    analyses = StoryAnalysisRepository(migrated_session_factory)
    analyses.save(
        project_id=project.id, prompt_version="story-v2", provider="test", model="test",
        analysis=StoryAnalysis(
            episode_summary="整剧摘要",
            explosions=tuple(
                ExplosionCandidate(
                    start_ms=index * 60_000, end_ms=index * 60_000 + 20_000,
                    title=f"高光 {index}", reason="冲突集中", score=95 - index,
                )
                for index in range(8)
            ),
            media_duration_ms=600_000,
        ),
    )

    with TestClient(_app(migrated_session_factory)) as client:
        created = client.post(
            f"/api/v1/projects/{project.id}/story-batches",
            headers=HEADERS,
            json={
                "target_count": 2, "min_duration_ms": 60_000, "max_duration_ms": 120_000,
                "burn_subtitles": True, "idempotency_key": "story-one",
            },
        )
        listed = client.get(f"/api/v1/projects/{project.id}/story-batches", headers=HEADERS)
        plans = client.get(f"/api/v1/projects/{project.id}/edit-plans", headers=HEADERS)

    assert created.status_code == 202
    payload = created.json()
    assert payload["job"]["job_type"] == "render_story_batch"
    assert payload["batch"]["status"] == "queued"
    assert len(payload["batch"]["items"]) == 2
    assert all(item["duration_ms"] >= 50_000 for item in payload["batch"]["items"])
    assert len(listed.json()) == 1
    assert len(plans.json()) == 2
    assert {plan["kind"] for plan in plans.json()} == {"story"}


def test_story_api_requires_analysis(migrated_session_factory, tmp_path: Path) -> None:
    projects = ProjectRepository(migrated_session_factory)
    project, _source = _project(projects, tmp_path, "未分析")

    with TestClient(_app(migrated_session_factory)) as client:
        response = client.post(
            f"/api/v1/projects/{project.id}/story-batches",
            headers=HEADERS,
            json={
                "target_count": 1, "min_duration_ms": 60_000, "max_duration_ms": 120_000,
                "burn_subtitles": True, "idempotency_key": "story-two",
            },
        )

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "analysis_required"


def test_story_api_rejects_media_shorter_than_minimum(
    migrated_session_factory, tmp_path: Path
) -> None:
    projects = ProjectRepository(migrated_session_factory)
    project, _source = _project(projects, tmp_path, "太短", duration_ms=30_000)
    analyses = StoryAnalysisRepository(migrated_session_factory)
    analyses.save(
        project_id=project.id, prompt_version="story-v2", provider="test", model="test",
        analysis=StoryAnalysis(episode_summary="短片", media_duration_ms=30_000),
    )

    with TestClient(_app(migrated_session_factory)) as client:
        response = client.post(
            f"/api/v1/projects/{project.id}/story-batches",
            headers=HEADERS,
            json={
                "target_count": 1, "min_duration_ms": 60_000, "max_duration_ms": 120_000,
                "burn_subtitles": True, "idempotency_key": "story-three",
            },
        )

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "insufficient_media"
