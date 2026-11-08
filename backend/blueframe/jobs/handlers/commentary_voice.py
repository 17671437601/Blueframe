from __future__ import annotations

from pathlib import PurePosixPath

from blueframe.commentary.captions import write_contextual_ass
from blueframe.commentary.repository import CommentaryRepository
from blueframe.commentary.voice import VoiceTimelineService, write_timeline_manifest
from blueframe.jobs.models import Job
from blueframe.projects.repository import ProjectRepository
from blueframe.security.project_paths import resolve_within_root
from blueframe.workers.protocol import JobResult, WorkerControl


class CommentaryVoiceHandler:
    def __init__(self, projects: ProjectRepository, scripts: CommentaryRepository, voice: VoiceTimelineService) -> None:
        self.projects, self.scripts, self.voice = projects, scripts, voice

    def run(self, job: Job, checkpoint: dict | None, control: WorkerControl) -> JobResult:
        project_id, script_id = str(job.payload["project_id"]), str(job.payload["script_id"])
        project, script = self.projects.get(project_id), self.scripts.get(script_id)
        if project is None or script is None or script.project_id != project_id:
            raise ValueError("项目或解说稿不存在")
        relative = PurePosixPath(project.output_relative_path) / ".blueframe" / "voice" / script.id
        output_root = resolve_within_root(project.root_path, relative.as_posix())
        control.progress(5, "synthesize_commentary")
        timeline = self.voice.synthesize(script, output_root)
        config = project.config.values
        write_contextual_ass(
            timeline, output_root / "captions.ass",
            width=int(config.get("output_width", 1080)), height=int(config.get("output_height", 1920)),
        )
        write_timeline_manifest(timeline, output_root / "timeline.json")
        control.progress(100, "align_commentary")
        return JobResult(artifacts=(script.id,))
