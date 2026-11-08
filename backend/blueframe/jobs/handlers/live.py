from __future__ import annotations

from blueframe.asr.models import AsrStatus
from blueframe.asr.service import AsrService
from blueframe.drama.analysis_service import AnalysisService
from blueframe.editing.models import EditPlanDraft, EditSegment, PlanKind
from blueframe.editing.repository import EditPlanRepository
from blueframe.jobs.models import Job
from blueframe.jobs.repository import JobRepository
from blueframe.media.probe import MediaInfo
from blueframe.projects.repository import ProjectRepository
from blueframe.security.project_paths import resolve_within_root
from blueframe.workers.protocol import JobResult, WorkerControl


class LiveSegmentProcessingHandler:
    def __init__(self, projects: ProjectRepository, asr: AsrService, analysis: AnalysisService, plans: EditPlanRepository, jobs: JobRepository, recordings) -> None:
        self.projects, self.asr, self.analysis, self.plans, self.jobs, self.recordings = projects, asr, analysis, plans, jobs, recordings

    def run(self, job: Job, checkpoint: dict | None, control: WorkerControl) -> JobResult:
        project_id, source_id, segment_id = str(job.payload["project_id"]), str(job.payload["source_id"]), str(job.payload["segment_id"])
        project, source = self.projects.get(project_id), self.projects.get_source(source_id)
        if project is None or source is None or source.project_id != project_id or source.media_info is None:
            raise ValueError("直播分段素材不存在")
        info = MediaInfo.model_validate(source.media_info)
        document = self.asr.transcribe(source, resolve_within_root(project.root_path, source.relative_path), info, control)
        ranges: list[tuple[int, int]] = []
        artifacts = [document.id]
        if document.status is AsrStatus.COMPLETED and document.lines:
            result = self.analysis.analyze(
                project_id=project_id, lines=document.lines, media_duration_ms=info.duration_ms,
                checkpoint=(checkpoint or {}).get("analysis"), control=control,
            )
            if result is None: return JobResult(artifacts=tuple(artifacts))
            artifacts.append(result.version.id)
            analysis = result.version.analysis
            if analysis.edit_candidates: ranges = list(analysis.edit_candidates[0].segments)
            elif analysis.explosions: ranges = [(item.start_ms, item.end_ms) for item in analysis.explosions]
        if not ranges: ranges = [(0, info.duration_ms)]
        segments = tuple(EditSegment(
            source_id=source.id, source_start_ms=max(0, start), source_end_ms=min(info.duration_ms, end),
            source_duration_ms=info.duration_ms,
        ) for start, end in ranges if min(info.duration_ms, end) - max(0, start) >= 500)
        if not segments: raise ValueError("直播分段没有可渲染范围")
        plan = self.plans.save(project_id, EditPlanDraft(
            title=f"直播切片 {source.order_index + 1}", kind=PlanKind.HIGHLIGHT,
            target_duration_ms=sum(item.duration_ms for item in segments), segments=segments,
        ), idempotency_key=f"live:{segment_id}:plan")
        render = self.jobs.create("render_edit_plan", {"project_id": project_id, "plan_id": plan.id}, f"live:{segment_id}:render")
        self.recordings.update_segment(segment_id, status="processed", size_bytes=self.recordings.get_segment(segment_id).size_bytes, duration_ms=info.duration_ms, fingerprint=self.recordings.get_segment(segment_id).fingerprint)
        return JobResult(artifacts=tuple([*artifacts, plan.id, render.id]))
