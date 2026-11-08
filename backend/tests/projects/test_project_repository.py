from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from blueframe.projects.models import ProjectType, SourceRegistration
from blueframe.projects.repository import ProjectRepository


NOW = datetime(2026, 11, 8, 9, 30, tzinfo=UTC)


def test_project_lifecycle_keeps_immutable_config_and_unicode_root(
    migrated_session_factory, tmp_path: Path
) -> None:
    repository = ProjectRepository(migrated_session_factory, clock=lambda: NOW)
    root = (tmp_path / "中文 项目").resolve()
    root.mkdir()

    created = repository.create(
        name="都市悬疑 第一季",
        project_type=ProjectType.DRAMA,
        root_path=root,
        output_relative_path="交付 文件",
        config={"target_seconds": 480, "explosion_threshold": 72},
        idempotency_key="create-drama-1",
    )
    duplicate = repository.create(
        name="ignored duplicate name",
        project_type=ProjectType.DRAMA,
        root_path=root,
        output_relative_path="other",
        config={"target_seconds": 30},
        idempotency_key="create-drama-1",
    )

    assert duplicate.id == created.id
    assert created.root_path == root
    assert created.config.version == 1
    assert created.config.values["target_seconds"] == 480
    assert repository.get(created.id) == created
    assert repository.list()[0].name == "都市悬疑 第一季"


def test_sources_preserve_order_distinguish_folders_and_reimport_idempotently(
    migrated_session_factory, tmp_path: Path
) -> None:
    repository = ProjectRepository(migrated_session_factory, clock=lambda: NOW)
    project = repository.create(
        name="多集项目",
        project_type=ProjectType.DRAMA,
        root_path=tmp_path.resolve(),
        output_relative_path="outputs",
        config={},
        idempotency_key="project-sources",
    )
    registrations = [
        SourceRegistration(
            relative_path="第一集/正片.mp4",
            size_bytes=100,
            modified_ns=10,
            content_fingerprint="same-content",
        ),
        SourceRegistration(
            relative_path="第二集/正片.mp4",
            size_bytes=100,
            modified_ns=11,
            content_fingerprint="same-content",
        ),
    ]

    first = repository.add_sources(project.id, registrations)
    second = repository.add_sources(project.id, registrations)

    assert [source.order_index for source in first] == [0, 1]
    assert [source.relative_path for source in first] == [
        "第一集/正片.mp4",
        "第二集/正片.mp4",
    ]
    assert [source.id for source in second] == [source.id for source in first]
    assert len(repository.list_sources(project.id)) == 2
