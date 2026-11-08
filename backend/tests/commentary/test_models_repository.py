from pathlib import Path

import pytest
from pydantic import ValidationError

from blueframe.commentary.models import CommentarySentence, SourceCitation
from blueframe.commentary.repository import CommentaryRepository
from blueframe.projects.models import ProjectType
from blueframe.projects.repository import ProjectRepository


def test_generated_sentence_requires_a_valid_source_citation() -> None:
    with pytest.raises(ValidationError):
        CommentarySentence(text="他终于发现了真相", citations=())

    manual = CommentarySentence(text="补充一句开场白", citations=(), manual=True)
    assert manual.manual is True


def test_commentary_repository_versions_manual_edits(migrated_session_factory) -> None:
    project_id = ProjectRepository(migrated_session_factory).create(
        name="Movie", project_type=ProjectType.MOVIE, root_path=Path("C:/movie"),
        output_relative_path="out", config={}, idempotency_key="commentary-project",
    ).id
    repository = CommentaryRepository(migrated_session_factory)
    citation = SourceCitation(source_id="source-a", start_ms=100, end_ms=900, quote="真相就在这里")
    first = repository.save(
        project_id=project_id, title="解说", voice="voice-a", prompt_version="commentary-v1",
        provider="fixture", model="m", sentences=(CommentarySentence(text="真相浮出水面", citations=(citation,)),),
    )
    second = repository.save(
        project_id=project_id, title=first.title, voice=first.voice, prompt_version="manual-edit",
        provider="manual", model="local", sentences=(CommentarySentence(text="人工开场", manual=True),),
    )

    assert (first.version, second.version) == (1, 2)
    assert [item.version for item in repository.list_for_project(project_id)] == [2, 1]
    assert repository.get(second.id).sentences[0].text == "人工开场"
