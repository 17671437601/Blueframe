from datetime import UTC, datetime
from pathlib import Path

from blueframe.jobs.models import Job, JobStatus
from blueframe.jobs.handlers.media import ProjectTranscriptionHandler
from blueframe.media.probe import MediaInfo
from blueframe.projects.models import ProjectType, SourceRegistration
from blueframe.projects.repository import ProjectRepository


NOW = datetime(2026, 11, 8, 12, 0, tzinfo=UTC)


class FakeAsrService:
    def __init__(self): self.calls = []
    def transcribe(self, source, source_path, media_info, control):
        self.calls.append((source, source_path, media_info))
        return type("Document", (), {"id": f"doc-{source.id}"})()


class Control:
    def __init__(self): self.saved = []
    def checkpoint(self, data): self.saved.append(data)
    def progress(self, *_args, **_kwargs): pass
    def heartbeat(self): pass
    pause_requested = False
    cancel_requested = False


def test_transcription_handler_resumes_after_completed_sources(
    migrated_session_factory, tmp_path: Path
) -> None:
    projects = ProjectRepository(migrated_session_factory, clock=lambda: NOW)
    project = projects.create(
        name="handler", project_type=ProjectType.DRAMA, root_path=tmp_path,
        output_relative_path="out", config={}, idempotency_key="handler",
    )
    paths = ["one.mp4", "two.mp4"]
    for path in paths: (tmp_path / path).touch()
    sources = projects.add_sources(project.id, [
        SourceRegistration(relative_path=path, size_bytes=1, modified_ns=index, content_fingerprint=path)
        for index, path in enumerate(paths)
    ])
    media = MediaInfo(
        duration_ms=1000, size_bytes=1, format_name="mp4", width=100,
        height=100, rotation=0, frame_rate=25, video_codec="h264",
        has_audio=True, audio_codec="aac", audio_sample_rate=16000, audio_channels=1,
    )
    for source in sources: projects.update_media_info(source.id, media.model_dump(mode="json"))
    service = FakeAsrService()
    handler = ProjectTranscriptionHandler(projects, service)
    job = Job(
        id="job", job_type="transcribe_project", payload={"project_id": project.id},
        status=JobStatus.RUNNING, progress=0, attempts=1, idempotency_key="key",
        created_at=NOW, updated_at=NOW,
    )
    control = Control()

    result = handler.run(job, {"completed_source_ids": [sources[0].id]}, control)

    assert [call[0].id for call in service.calls] == [sources[1].id]
    assert result.artifacts == (f"doc-{sources[1].id}",)
    assert control.saved[-1]["completed_source_ids"] == [sources[0].id, sources[1].id]
