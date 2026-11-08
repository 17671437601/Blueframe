from pathlib import Path

import pytest

from blueframe.live.models import LivePlatform
from blueframe.live.repository import RecordingRepository
from blueframe.projects.models import ProjectType
from blueframe.projects.repository import ProjectRepository


def project(session_factory, key):
    return ProjectRepository(session_factory).create(name=key, project_type=ProjectType.LIVE, root_path=Path(f"C:/{key}"), output_relative_path="out", config={}, idempotency_key=key).id


def test_recording_requires_explicit_rights_confirmation(migrated_session_factory) -> None:
    repository = RecordingRepository(migrated_session_factory, concurrency_limit=2)
    with pytest.raises(ValueError, match="authorization"):
        repository.create(project_id=project(migrated_session_factory, "live-a"), platform=LivePlatform.DOUYIN,
                          display_name="主播", source_reference="credential:a", authorization_confirmed=False)


def test_concurrency_is_enforced_and_restart_restores_intent_not_process(migrated_session_factory) -> None:
    repository = RecordingRepository(migrated_session_factory, concurrency_limit=1)
    first = repository.create(project_id=project(migrated_session_factory, "live-one"), platform=LivePlatform.DOUYIN,
                              display_name="主播一", source_reference="credential:a", authorization_confirmed=True)
    repository.mark_recording(first.id)
    with pytest.raises(RuntimeError, match="concurrency"):
        repository.create(project_id=project(migrated_session_factory, "live-two"), platform=LivePlatform.DOUYIN,
                          display_name="主播二", source_reference="credential:b", authorization_confirmed=True)
    recovered = repository.recover_intents()
    assert recovered[0].status == "interrupted"
    assert recovered[0].intent_active is True
    assert recovered[0].process_id is None
