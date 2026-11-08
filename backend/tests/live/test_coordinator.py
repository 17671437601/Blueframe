from pathlib import Path

from blueframe.jobs.repository import JobRepository
from blueframe.live.coordinator import StableSegmentCoordinator
from blueframe.live.models import LivePlatform
from blueframe.live.repository import RecordingRepository
from blueframe.projects.models import ProjectType
from blueframe.projects.repository import ProjectRepository


class Info:
    duration_ms = 60_000
    size_bytes = 7
    def model_dump(self, mode="json"): return {"duration_ms": self.duration_ms, "size_bytes": self.size_bytes, "has_audio": True, "rotation": 0}


def test_stable_segment_is_enqueued_once_after_two_identical_observations(migrated_session_factory, tmp_path: Path) -> None:
    projects = ProjectRepository(migrated_session_factory)
    project = projects.create(name="Live", project_type=ProjectType.LIVE, root_path=tmp_path, output_relative_path="out", config={}, idempotency_key="live-coordinator")
    recordings = RecordingRepository(migrated_session_factory)
    session = recordings.create(project_id=project.id, platform=LivePlatform.DOUYIN, display_name="主播", source_reference="secret", authorization_confirmed=True)
    segment_root = tmp_path / "out" / "live" / session.id; segment_root.mkdir(parents=True)
    segment = segment_root / "segment-000000.mkv"; segment.write_bytes(b"content")
    jobs = JobRepository(migrated_session_factory)
    coordinator = StableSegmentCoordinator(recordings, projects, jobs, media_probe=lambda _path: Info())

    assert coordinator.scan(session.id, segment_root) == []
    queued = coordinator.scan(session.id, segment_root)
    assert len(queued) == 1
    assert queued[0].job_type == "process_live_segment"
    assert coordinator.scan(session.id, segment_root) == []
    assert len([job for job in jobs.list() if job.job_type == "process_live_segment"]) == 1
