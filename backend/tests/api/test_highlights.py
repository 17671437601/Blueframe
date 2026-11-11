from pathlib import Path

from fastapi.testclient import TestClient

from blueframe.app import create_app
from blueframe.asr.repository import AsrRepository
from blueframe.auth.service import StandaloneAccountService
from blueframe.drama.models import ExplosionCandidate, StoryAnalysis
from blueframe.drama.repository import StoryAnalysisRepository
from blueframe.highlights.repository import HighlightBatchRepository
from blueframe.jobs.repository import JobRepository
from blueframe.projects.models import ProjectType, SourceRegistration
from blueframe.projects.repository import ProjectRepository

HEADERS = {"X-BlueFrame-Session": "a" * 64}


def _project(projects: ProjectRepository, tmp_path: Path, name: str):
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
        registered.id, {"duration_ms": 300_000, "has_audio": True, "rotation": 0}
    )
    return project, registered


def _app(session_factory):
    return create_app(
        session_token="a" * 64,
        project_repository=ProjectRepository(session_factory),
        analysis_repository=StoryAnalysisRepository(session_factory),
        highlight_batch_repository=HighlightBatchRepository(session_factory),
        job_repository=JobRepository(session_factory),
        account_service=StandaloneAccountService(),
        asr_repository=AsrRepository(session_factory),
    )


def test_highlight_api_plans_clips_and_queues_single_batch_job(
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
                    start_ms=index * 40_000, end_ms=index * 40_000 + 12_000,
                    title=f"高光 {index}", reason="冲突集中", score=95 - index,
                )
                for index in range(4)
            ),
            media_duration_ms=300_000,
        ),
    )

    with TestClient(_app(migrated_session_factory)) as client:
        created = client.post(
            f"/api/v1/projects/{project.id}/highlight-batches",
            headers=HEADERS,
            json={
                "target_count": 3, "min_duration_ms": 8_000, "max_duration_ms": 20_000,
                "burn_subtitles": True, "idempotency_key": "highlight-one",
            },
        )
        listed = client.get(f"/api/v1/projects/{project.id}/highlight-batches", headers=HEADERS)

    assert created.status_code == 202
    payload = created.json()
    assert payload["job"]["job_type"] == "render_highlights"
    assert payload["batch"]["status"] == "queued"
    assert len(payload["batch"]["clips"]) == 3
    assert [clip["score"] for clip in payload["batch"]["clips"]] == [95, 94, 93]
    assert "output_path" not in created.text
    assert len(listed.json()) == 1


def test_highlight_api_requires_analysis(migrated_session_factory, tmp_path: Path) -> None:
    projects = ProjectRepository(migrated_session_factory)
    project, _source = _project(projects, tmp_path, "未分析")

    with TestClient(_app(migrated_session_factory)) as client:
        response = client.post(
            f"/api/v1/projects/{project.id}/highlight-batches",
            headers=HEADERS,
            json={
                "target_count": 5, "min_duration_ms": 8_000, "max_duration_ms": 20_000,
                "burn_subtitles": True, "idempotency_key": "highlight-two",
            },
        )

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "analysis_required"
