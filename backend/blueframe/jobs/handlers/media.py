from __future__ import annotations

from blueframe.asr.service import AsrService
from blueframe.jobs.models import Job
from blueframe.media.probe import MediaInfo
from blueframe.projects.repository import ProjectRepository
from blueframe.security.project_paths import resolve_within_root
from blueframe.workers.protocol import JobResult, WorkerControl


class ProjectTranscriptionHandler:
    def __init__(self, projects: ProjectRepository, asr: AsrService) -> None:
        self.projects = projects
        self.asr = asr

    def run(
        self,
        job: Job,
        checkpoint: dict | None,
        control: WorkerControl,
    ) -> JobResult:
        project_id = str(job.payload["project_id"])
        project = self.projects.get(project_id)
        if project is None:
            raise ValueError("项目不存在")
        completed = list((checkpoint or {}).get("completed_source_ids", []))
        completed_set = set(completed)
        artifacts: list[str] = []
        sources = self.projects.list_sources(project_id)
        total = max(1, len(sources))
        for index, source in enumerate(sources):
            if source.id in completed_set:
                continue
            if control.pause_requested or control.cancel_requested:
                break
            if source.media_info is None:
                raise ValueError(f"素材尚未完成探测: {source.relative_path}")
            source_path = resolve_within_root(project.root_path, source.relative_path)
            document = self.asr.transcribe(
                source,
                source_path,
                MediaInfo.model_validate(source.media_info),
                control,
            )
            artifacts.append(document.id)
            completed.append(source.id)
            completed_set.add(source.id)
            control.checkpoint(
                {
                    "completed_source_ids": completed,
                    "last_document_id": document.id,
                }
            )
            control.progress((index + 1) / total * 100, "transcribe_project")
            control.heartbeat()
        return JobResult(artifacts=tuple(artifacts))
