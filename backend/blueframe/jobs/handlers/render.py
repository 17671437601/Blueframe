from __future__ import annotations

import re
from pathlib import PurePosixPath

from blueframe.editing.repository import EditPlanRepository
from blueframe.jobs.models import Job
from blueframe.projects.repository import ProjectRepository
from blueframe.rendering.graph import RenderInput, RenderSegment, RenderSpec
from blueframe.rendering.service import RenderService
from blueframe.security.project_paths import resolve_within_root
from blueframe.workers.protocol import JobResult, WorkerControl


class RenderProjectHandler:
    def __init__(self, projects: ProjectRepository, plans: EditPlanRepository, render: RenderService, ffmpeg) -> None:
        self.projects, self.plans, self.render, self.ffmpeg = projects, plans, render, ffmpeg

    def run(self, job: Job, checkpoint: dict | None, control: WorkerControl) -> JobResult:
        project_id = str(job.payload["project_id"])
        plan_id = str(job.payload["plan_id"])
        project = self.projects.get(project_id)
        plan = self.plans.get(plan_id)
        if project is None or plan is None or plan.project_id != project_id:
            raise ValueError("项目或剪辑方案不存在")
        sources = {source.id: source for source in self.projects.list_sources(project_id)}
        required = {segment.source_id for segment in plan.segments}
        if not required <= sources.keys():
            raise ValueError("剪辑方案引用了不存在的素材")
        inputs = []
        for source_id in sorted(required):
            source = sources[source_id]
            if source.media_info is None:
                raise ValueError("素材尚未完成探测")
            inputs.append(RenderInput(
                source_id=source_id,
                path=resolve_within_root(project.root_path, source.relative_path),
                has_audio=bool(source.media_info.get("has_audio")),
                rotation=int(source.media_info.get("rotation") or 0),
            ))
        safe_title = re.sub(r"[^0-9A-Za-z\u4e00-\u9fff_-]+", "-", plan.title).strip("-") or "成片"
        relative_output = PurePosixPath(project.output_relative_path) / f"{safe_title}-v{plan.version}.mp4"
        output = resolve_within_root(project.root_path, relative_output.as_posix())
        config = project.config.values
        artifact = self.render.render(
            job_id=job.id, project_id=project_id, plan_id=plan_id,
            spec=RenderSpec(
                ffmpeg=self.ffmpeg, output=output,
                width=int(config.get("output_width", 1080)),
                height=int(config.get("output_height", 1920)),
                fps=int(config.get("output_fps", 30)),
                inputs=tuple(inputs),
                segments=tuple(RenderSegment(
                    source_id=segment.source_id, start_ms=segment.source_start_ms,
                    end_ms=segment.source_end_ms,
                ) for segment in plan.segments),
            ),
            control=control,
        )
        return JobResult(artifacts=(artifact.id,))
