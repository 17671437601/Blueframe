from datetime import UTC, datetime
from pathlib import Path

from blueframe.commentary.models import CommentarySentence
from blueframe.commentary.repository import CommentaryRepository
from blueframe.commentary.voice import VoiceTimelineService, load_timeline_manifest
from blueframe.domain.common import ProviderUsage
from blueframe.jobs.handlers.commentary_voice import CommentaryVoiceHandler
from blueframe.jobs.models import Job, JobStatus
from blueframe.projects.models import ProjectType
from blueframe.projects.repository import ProjectRepository
from blueframe.providers.tts import TtsResult


class Tts:
    async def synthesize(self, request):
        request.output_root.mkdir(parents=True, exist_ok=True)
        path = request.output_root / request.filename; path.write_bytes(b"voice")
        return TtsResult(provider="fixture", audio_path=path, duration_ms=900, usage=ProviderUsage(input_units=1, output_units=1))


class Assembler:
    def assemble(self, inputs, output): output.write_bytes(b"joined")


class Control:
    pause_requested = cancel_requested = False
    def progress(self, *_args): pass
    def heartbeat(self): pass
    def checkpoint(self, *_args): pass


def test_voice_handler_persists_timeline_and_contextual_captions(migrated_session_factory, tmp_path: Path) -> None:
    projects = ProjectRepository(migrated_session_factory)
    project = projects.create(name="Movie", project_type=ProjectType.MOVIE, root_path=tmp_path, output_relative_path="out", config={}, idempotency_key="voice-project")
    scripts = CommentaryRepository(migrated_session_factory)
    script = scripts.save(
        project_id=project.id, title="解说", voice="voice-a", prompt_version="manual",
        provider="manual", model="local", sentences=(CommentarySentence(text="人工解说。", manual=True),),
    )
    job = Job(id="job-a", job_type="synthesize_commentary", status=JobStatus.RUNNING, progress=0, attempts=0,
              payload={"project_id": project.id, "script_id": script.id}, idempotency_key="voice-one",
              created_at=datetime.now(UTC), updated_at=datetime.now(UTC))
    result = CommentaryVoiceHandler(projects, scripts, VoiceTimelineService(Tts(), Assembler())).run(job, None, Control())

    manifest = tmp_path / "out" / ".blueframe" / "voice" / script.id / "timeline.json"
    timeline = load_timeline_manifest(manifest)
    assert timeline.duration_ms == 900
    assert (manifest.parent / "captions.ass").is_file()
    assert result.artifacts == (script.id,)
