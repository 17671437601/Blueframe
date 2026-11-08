from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from blueframe.asr.models import AsrStatus, EngineSegment
from blueframe.asr.repository import AsrRepository
from blueframe.asr.service import AsrService
from blueframe.media.probe import MediaInfo
from blueframe.projects.models import ProjectSource, ProjectType, SourceRegistration
from blueframe.projects.repository import ProjectRepository


NOW = datetime(2026, 11, 8, 10, 0, tzinfo=UTC)


class FakeEngine:
    def __init__(self, model_version="paraformer-v1") -> None:
        self.model_version = model_version
        self.calls = 0

    def transcribe(self, _audio_path: Path):
        self.calls += 1
        return [
            EngineSegment(start_ms=0, end_ms=800, text="第一句。"),
            EngineSegment(start_ms=900, end_ms=1600, text="第二句。"),
        ]


class FakeControl:
    def __init__(self) -> None:
        self.checkpoints = []
        self.progresses = []

    def checkpoint(self, data): self.checkpoints.append(data)
    def progress(self, value, stage=None): self.progresses.append((value, stage))
    def heartbeat(self): pass
    @property
    def pause_requested(self): return False
    @property
    def cancel_requested(self): return False


def persisted_source(session_factory, root: Path, key: str) -> ProjectSource:
    projects = ProjectRepository(session_factory, clock=lambda: NOW)
    project = projects.create(
        name="ASR 测试", project_type=ProjectType.DRAMA, root_path=root,
        output_relative_path="outputs", config={}, idempotency_key=key,
    )
    return projects.add_sources(project.id, [SourceRegistration(
        relative_path="第一集.mp4", size_bytes=123, modified_ns=456,
        content_fingerprint="segment-hash",
    )])[0]


def info(has_audio=True) -> MediaInfo:
    return MediaInfo(
        duration_ms=2000, size_bytes=123, format_name="mp4", width=1280,
        height=720, rotation=0, frame_rate=25, video_codec="h264",
        has_audio=has_audio, audio_codec="aac" if has_audio else None,
        audio_sample_rate=48000 if has_audio else None,
        audio_channels=2 if has_audio else None,
    )


def test_transcription_is_cached_checkpointed_and_model_versioned(
    migrated_session_factory, tmp_path: Path
) -> None:
    repository = AsrRepository(migrated_session_factory, clock=lambda: NOW)
    media_source = persisted_source(migrated_session_factory, tmp_path, "asr-cache")
    engine = FakeEngine()
    extracted = []

    def extract(_source, output):
        extracted.append(output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.touch()
        return output

    control = FakeControl()
    service = AsrService(repository, engine, audio_extractor=extract)
    first = service.transcribe(media_source, tmp_path / "第一集.mp4", info(), control)
    cached = service.transcribe(media_source, tmp_path / "第一集.mp4", info(), control)

    assert first == cached
    assert first.status == AsrStatus.COMPLETED
    assert [line.text for line in first.lines] == ["第一句。", "第二句。"]
    assert engine.calls == 1 and len(extracted) == 1
    assert control.checkpoints[-1]["asr_document_id"] == first.id

    upgraded = FakeEngine("paraformer-v2")
    AsrService(repository, upgraded, audio_extractor=extract).transcribe(
        media_source, tmp_path / "第一集.mp4", info(), FakeControl()
    )
    assert upgraded.calls == 1


def test_no_audio_is_persisted_without_invoking_engine(
    migrated_session_factory, tmp_path: Path
) -> None:
    repository = AsrRepository(migrated_session_factory, clock=lambda: NOW)
    media_source = persisted_source(migrated_session_factory, tmp_path, "asr-no-audio")
    engine = FakeEngine()
    service = AsrService(repository, engine, audio_extractor=lambda *_: None)

    document = service.transcribe(media_source, tmp_path / "silent.mp4", info(False), FakeControl())

    assert document.status == AsrStatus.NO_AUDIO
    assert document.lines == ()
    assert engine.calls == 0
