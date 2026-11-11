from __future__ import annotations

import re
from pathlib import Path, PurePosixPath

from blueframe.asr.repository import AsrRepository
from blueframe.editing.repository import EditPlanRepository
from blueframe.jobs.models import Job
from blueframe.projects.repository import ProjectRepository
from blueframe.rendering.graph import RenderInput, RenderSegment, RenderSpec
from blueframe.rendering.service import RenderService
from blueframe.security.project_paths import resolve_within_root
from blueframe.story.captions import write_story_ass
from blueframe.story.repository import StoryBatchRepository
from blueframe.workers.protocol import JobResult, WorkerControl


class StoryBatchHandler:
    def __init__(
        self,
        projects: ProjectRepository,
        batches: StoryBatchRepository,
        plans: EditPlanRepository,
        asr: AsrRepository,
        render: RenderService,
        ffmpeg: Path,
    ) -> None:
        self.projects, self.batches, self.plans, self.asr, self.render, self.ffmpeg = (
            projects, batches, plans, asr, render, ffmpeg,
        )

    def run(self, job: Job, checkpoint: dict | None, control: WorkerControl) -> JobResult:
        batch = self.batches.get(str(job.payload["batch_id"]))
        if batch is None:
            raise ValueError("主线成片批次不存在")
        project = self.projects.get(batch.project_id)
        if project is None:
            raise ValueError("项目不存在")
        sources = {source.id: source for source in self.projects.list_sources(batch.project_id)}
        documents = {
            document.source_id: document.lines
            for document in self.asr.list_for_project(batch.project_id)
        }
        pending = [item for item in batch.items if item.status in {"queued", "failed"}]
        total = max(len(batch.items), 1)
        config = project.config.values
        width = int(config.get("output_width", 1080))
        height = int(config.get("output_height", 1920))
        fps = int(config.get("output_fps", 30))
        self.batches.set_status(batch.id, "running")

        for item in pending:
            if control.pause_requested or control.cancel_requested:
                self.batches.set_status(batch.id, "paused" if control.pause_requested else "cancelled")
                control.checkpoint({"batch_id": batch.id, "next_index": item.item_index})
                return JobResult(artifacts=(batch.id,))
            self.batches.update_item(item.id, status="running")
            item_job_id = f"{job.id}-{item.item_index:03d}"
            try:
                plan = None if item.plan_id is None else self.plans.get(item.plan_id)
                if plan is None:
                    raise ValueError("剪辑方案缺失")
                required = {segment.source_id for segment in plan.segments}
                inputs: list[RenderInput] = []
                for source_id in sorted(required):
                    source = sources.get(source_id)
                    if source is None or source.media_info is None:
                        raise ValueError("片段素材不可用")
                    inputs.append(
                        RenderInput(
                            source_id=source.id,
                            path=resolve_within_root(project.root_path, source.relative_path),
                            has_audio=bool(source.media_info.get("has_audio")),
                            rotation=int(source.media_info.get("rotation") or 0),
                        )
                    )
                relative_output = PurePosixPath(project.output_relative_path) / "story"
                output = resolve_within_root(
                    project.root_path,
                    (
                        relative_output
                        / f"{item.item_index + 1:03d}-{_safe_name(item.title)}.mp4"
                    ).as_posix(),
                )
                subtitle_path = None
                if batch.burn_subtitles:
                    relative_ass = (
                        relative_output
                        / ".blueframe-work"
                        / item_job_id
                        / f"story-{item.item_index:03d}.ass"
                    )
                    subtitle_path = write_story_ass(
                        plan.segments,
                        documents,
                        resolve_within_root(project.root_path, relative_ass.as_posix()),
                        width=width,
                        height=height,
                    )
                artifact = self.render.render(
                    job_id=item_job_id,
                    project_id=batch.project_id,
                    plan_id=plan.id,
                    spec=RenderSpec(
                        ffmpeg=self.ffmpeg,
                        output=output,
                        width=width,
                        height=height,
                        fps=fps,
                        inputs=tuple(inputs),
                        segments=tuple(
                            RenderSegment(
                                source_id=segment.source_id,
                                start_ms=segment.source_start_ms,
                                end_ms=segment.source_end_ms,
                            )
                            for segment in plan.segments
                        ),
                        subtitle_path=subtitle_path,
                    ),
                    control=_ScaledControl(control, index=item.item_index, total=total),
                )
                if artifact.status != "completed":
                    self.batches.update_item(item.id, status="queued")
                    self.batches.set_status(
                        batch.id, "paused" if control.pause_requested else "cancelled"
                    )
                    return JobResult(artifacts=(batch.id,))
                self.batches.update_item(
                    item.id, status="completed", output_path=artifact.published_path
                )
            except Exception as error:
                self.batches.update_item(item.id, status="failed", error_summary=_summarize(error))
            done = sum(1 for entry in self.batches.get(batch.id).items if entry.status == "completed")
            control.progress(done / total * 100, "render_story_batch")
            control.heartbeat()

        final = self.batches.finish(batch.id)
        return JobResult(artifacts=(final.id,))


class _ScaledControl:
    def __init__(self, inner: WorkerControl, *, index: int, total: int) -> None:
        self._inner = inner
        self._index = index
        self._total = max(total, 1)

    def progress(self, value: float, stage: str | None = None) -> None:
        overall = (self._index + max(0.0, min(value, 100.0)) / 100) / self._total * 100
        self._inner.progress(min(100.0, overall), stage)

    def heartbeat(self) -> None:
        self._inner.heartbeat()

    def checkpoint(self, data: dict) -> None:
        self._inner.checkpoint(data)

    @property
    def pause_requested(self) -> bool:
        return self._inner.pause_requested

    @property
    def cancel_requested(self) -> bool:
        return self._inner.cancel_requested


def _safe_name(title: str) -> str:
    cleaned = re.sub(r"[^0-9A-Za-z\u4e00-\u9fff_-]+", "-", title).strip("-")
    return (cleaned or "主线成片")[:30]


def _summarize(error: Exception) -> str:
    return " ".join(str(error).splitlines())[:300]
