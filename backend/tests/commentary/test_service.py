from pathlib import Path

import pytest

from blueframe.asr.models import AsrDocument, AsrLine, AsrStatus
from blueframe.commentary.repository import CommentaryRepository
from blueframe.commentary.service import CommentaryService
from blueframe.commentary.models import CommentarySentence
from blueframe.domain.common import ProviderUsage
from blueframe.projects.models import ProjectType
from blueframe.projects.repository import ProjectRepository
from blueframe.providers.ai import AiResult


class SequenceProvider:
    def __init__(self, outputs): self.outputs, self.calls = list(outputs), []
    async def execute(self, request):
        self.calls.append(request)
        return AiResult(provider="fixture", model="m", usage=ProviderUsage(input_units=1, output_units=1), output=self.outputs.pop(0))


def project(session_factory):
    return ProjectRepository(session_factory).create(
        name="Movie", project_type=ProjectType.MOVIE, root_path=Path("C:/movie"),
        output_relative_path="out", config={}, idempotency_key="commentary-service-project",
    ).id


def document(text="凶手留下了蓝色纽扣"):
    return AsrDocument(
        id="doc", source_id="source-a", cache_key="key", model_version="v", language="zh",
        duration_ms=2000, status=AsrStatus.COMPLETED,
        lines=(AsrLine(index=0, start_ms=0, end_ms=2000, text=text),),
    )


def output(quote="凶手留下了蓝色纽扣"):
    return {"title": "真相解说", "sentences": [{"text": "一个细节暴露了凶手。", "citations": [{
        "source_id": "source-a", "start_ms": 0, "end_ms": 2000, "quote": quote,
    }]}]}


def test_service_generates_traceable_script_and_chunks(migrated_session_factory) -> None:
    provider = SequenceProvider([output(), output()])
    service = CommentaryService(provider, CommentaryRepository(migrated_session_factory), max_chunk_characters=12)

    script = service.generate(project_id=project(migrated_session_factory), documents=(document(), document("第二段剧情继续推进")), voice="voice-a")

    assert len(provider.calls) == 2
    assert script.version == 1
    assert all(sentence.citations for sentence in script.sentences)


def test_service_rejects_unverifiable_quote(migrated_session_factory) -> None:
    service = CommentaryService(SequenceProvider([output("并不存在的台词")]), CommentaryRepository(migrated_session_factory))
    with pytest.raises(ValueError, match="citation"):
        service.generate(project_id=project(migrated_session_factory), documents=(document(),), voice="voice-a")


def test_silent_movie_creates_editable_empty_script(migrated_session_factory) -> None:
    provider = SequenceProvider([])
    service = CommentaryService(provider, CommentaryRepository(migrated_session_factory))
    silent = AsrDocument(id="silent", source_id="source-a", cache_key="key", model_version="v", language="zh", duration_ms=2000, status=AsrStatus.NO_AUDIO)

    script = service.generate(project_id=project(migrated_session_factory), documents=(silent,), voice="voice-a")

    assert script.sentences == ()
    assert provider.calls == []


def test_regeneration_replaces_only_selected_sentence_and_creates_version(migrated_session_factory) -> None:
    repository = CommentaryRepository(migrated_session_factory)
    service = CommentaryService(SequenceProvider([output()]), repository)
    project_id = project(migrated_session_factory)
    base = repository.save(
        project_id=project_id, title="初稿", voice="voice-a", prompt_version="fixture",
        provider="fixture", model="m", sentences=(
            CommentarySentence.model_validate(output()["sentences"][0]),
            CommentarySentence(text="人工结尾", manual=True),
        ),
    )

    revised = service.regenerate_sentence(base=base, sentence_index=0, documents=(document(),))

    assert revised.version == 2
    assert revised.sentences[1].text == "人工结尾"
    assert revised.sentences[0].citations[0].quote == "凶手留下了蓝色纽扣"
