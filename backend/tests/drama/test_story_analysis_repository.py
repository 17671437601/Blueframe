from __future__ import annotations

from pathlib import Path

from blueframe.drama.repository import StoryAnalysisRepository
from blueframe.drama.models import Character, StoryAnalysis
from blueframe.projects.models import ProjectType
from blueframe.projects.repository import ProjectRepository


def analysis() -> StoryAnalysis:
    return StoryAnalysis(
        episode_summary="summary",
        characters=(Character(name="林夏", role="主角", description="记者"),),
        media_duration_ms=10_000,
    )


def test_repository_preserves_versions_and_locks_accepted_result(
    migrated_session_factory,
) -> None:
    repository = StoryAnalysisRepository(migrated_session_factory)
    ProjectRepository(migrated_session_factory).create(
        name="Test", project_type=ProjectType.DRAMA, root_path=Path("C:/work"),
        output_relative_path="out", config={}, idempotency_key="analysis-project",
    )
    project_id = ProjectRepository(migrated_session_factory).list()[0].id
    first = repository.save(
        project_id=project_id, prompt_version="story-v1", provider="fixture",
        model="m1", analysis=analysis(),
    )
    second = repository.save(
        project_id=project_id, prompt_version="story-v2", provider="fixture",
        model="m2", analysis=analysis(),
    )
    accepted = repository.accept(project_id=project_id, version=1)

    assert (first.version, second.version, accepted.accepted) == (1, 2, True)
    assert [item.version for item in repository.list_for_project(project_id)] == [2, 1]
    assert repository.accept(project_id=project_id, version=2).version == 1
