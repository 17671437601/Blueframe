from pathlib import Path

from blueframe.editing.models import EditPlanDraft, EditSegment, PlanKind
from blueframe.editing.repository import EditPlanRepository
from blueframe.projects.models import ProjectType
from blueframe.projects.repository import ProjectRepository


def test_edit_plan_versions_coexist_and_save_is_idempotent(migrated_session_factory, tmp_path: Path) -> None:
    project = ProjectRepository(migrated_session_factory).create(
        name="Edit", project_type=ProjectType.DRAMA, root_path=tmp_path,
        output_relative_path="out", config={}, idempotency_key="edit-project",
    )
    repository = EditPlanRepository(migrated_session_factory)
    draft = EditPlanDraft(
        title="高光一", kind=PlanKind.HIGHLIGHT, target_duration_ms=3000,
        segments=(EditSegment(source_id="s1", source_start_ms=1000, source_end_ms=4000, source_duration_ms=10_000),),
    )
    first = repository.save(project.id, draft, idempotency_key="draft-one")
    same = repository.save(project.id, draft, idempotency_key="draft-one")
    second = repository.save(project.id, draft.model_copy(update={"title": "高光二"}), idempotency_key="draft-two")

    assert first.id == same.id
    assert (first.version, second.version) == (1, 2)
    assert [item.version for item in repository.list_for_project(project.id)] == [2, 1]
