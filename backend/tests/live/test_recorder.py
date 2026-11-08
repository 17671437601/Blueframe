from datetime import UTC, datetime
from pathlib import Path

from blueframe.auth.credential_store import InMemoryCredentialStore
from blueframe.live.platform import AuthorizedUrlAdapter
from blueframe.live.recorder import RecordingEngine, build_recording_command, redact_stream_secret
from blueframe.live.repository import RecordingRepository
from blueframe.projects.models import ProjectType
from blueframe.projects.repository import ProjectRepository


class Process:
    pid = 4321
    def __init__(self): self.stopped = False; self.returncode = None
    def poll(self): return self.returncode
    def stop(self): self.stopped = True; self.returncode = 0


class Launcher:
    def __init__(self): self.commands = []; self.process = Process()
    def start(self, command): self.commands.append(command); return self.process


def setup(session_factory, tmp_path):
    project = ProjectRepository(session_factory).create(name="Live", project_type=ProjectType.LIVE, root_path=tmp_path, output_relative_path="out", config={}, idempotency_key="live-recorder")
    credentials = InMemoryCredentialStore(); reference = credentials.put("live", "https://stream.example/live.flv?token=top-secret")
    repository = RecordingRepository(session_factory)
    session = repository.create(project_id=project.id, platform="douyin", display_name="主播", source_reference=reference, authorization_confirmed=True)
    return repository, session, credentials


def test_recording_command_reconnects_and_never_overwrites_sequence(tmp_path: Path) -> None:
    command = build_recording_command(Path("ffmpeg"), "https://example/live.flv", tmp_path, segment_seconds=60, start_number=17)
    assert command[command.index("-segment_start_number") + 1] == "17"
    assert "-reconnect" in command and "-segment_time" in command
    assert command[-1].endswith("segment-%06d.mkv")


def test_engine_starts_authorized_stream_and_gracefully_stops(migrated_session_factory, tmp_path: Path) -> None:
    repository, session, credentials = setup(migrated_session_factory, tmp_path)
    launcher = Launcher()
    engine = RecordingEngine(repository, AuthorizedUrlAdapter(credentials), launcher, Path("ffmpeg"), clock=lambda: datetime(2026, 1, 1, tzinfo=UTC))
    engine.start(session.id, tmp_path / "segments")
    assert repository.get(session.id).process_id == 4321
    assert "top-secret" in " ".join(launcher.commands[0])
    engine.stop(session.id)
    assert launcher.process.stopped is True
    assert repository.get(session.id).intent_active is False


def test_stream_secrets_are_redacted_from_errors() -> None:
    url = "https://stream.example/live.flv?token=top-secret"
    assert "top-secret" not in redact_stream_secret(f"failed to open {url}", url)
