from __future__ import annotations

import hashlib
from pathlib import Path

from blueframe.jobs.repository import JobRepository
from blueframe.live.repository import RecordingRepository
from blueframe.projects.models import SourceRegistration
from blueframe.projects.repository import ProjectRepository


class StableSegmentCoordinator:
    def __init__(self, recordings: RecordingRepository, projects: ProjectRepository, jobs: JobRepository, *, media_probe) -> None:
        self.recordings, self.projects, self.jobs, self.media_probe = recordings, projects, jobs, media_probe
        self._observations: dict[Path, tuple[int, int, int]] = {}

    def scan(self, session_id: str, segment_root: Path):
        session = self.recordings.get(session_id)
        project = None if session is None else self.projects.get(session.project_id)
        if session is None or project is None: raise ValueError("live session project is unavailable")
        queued = []
        known_paths = {item.path.resolve(): item for item in self.recordings.list_segments(session_id)}
        for path in sorted(segment_root.glob("segment-*.mkv")):
            resolved = path.resolve()
            if not resolved.is_relative_to(project.root_path.resolve()): continue
            stat = resolved.stat(); previous = self._observations.get(resolved)
            count = 1 if previous is None or previous[:2] != (stat.st_size, stat.st_mtime_ns) else previous[2] + 1
            self._observations[resolved] = (stat.st_size, stat.st_mtime_ns, count)
            sequence = int(path.stem.rsplit("-", 1)[-1])
            segment = known_paths.get(resolved) or self.recordings.add_segment(session_id=session_id, sequence=sequence, path=resolved)
            if segment.status in {"queued", "processed", "duplicate"} or count < 2 or stat.st_size <= 0: continue
            try: info = self.media_probe(resolved)
            except Exception: continue
            if int(info.duration_ms) < 1000: continue
            fingerprint = _sha256(resolved)
            duplicate = self.recordings.find_segment_by_fingerprint(fingerprint)
            if duplicate is not None and duplicate.id != segment.id:
                self.recordings.update_segment(segment.id, status="duplicate", size_bytes=stat.st_size, duration_ms=info.duration_ms, fingerprint=fingerprint)
                continue
            relative = resolved.relative_to(project.root_path.resolve()).as_posix()
            source = self.projects.add_sources(project.id, [SourceRegistration(
                relative_path=relative, size_bytes=stat.st_size, modified_ns=stat.st_mtime_ns,
                content_fingerprint=fingerprint,
            )])[0]
            self.projects.update_media_info(source.id, info.model_dump(mode="json"))
            self.recordings.update_segment(segment.id, status="queued", size_bytes=stat.st_size, duration_ms=info.duration_ms, fingerprint=fingerprint)
            queued.append(self.jobs.create(
                "process_live_segment", {"project_id": project.id, "source_id": source.id, "segment_id": segment.id},
                f"live-segment:{fingerprint}",
            ))
        return queued


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""): digest.update(block)
    return digest.hexdigest()
