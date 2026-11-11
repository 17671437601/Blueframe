from __future__ import annotations

import re
from pathlib import Path, PurePosixPath

from blueframe.asr.repository import AsrRepository
from blueframe.highlights.captions import write_clip_ass
from blueframe.highlights.repository import HighlightBatchRepository
from blueframe.jobs.models import Job
from blueframe.projects.repository import ProjectRepository
from blueframe.rendering.graph import RenderInput, RenderSegment, RenderSpec
from blueframe.rendering.service import RenderService
from blueframe.security.project_paths import resolve_within_root
from blueframe.workers.protocol import JobResult, WorkerControl


class HighlightBatchHandler:
    def __init__(
        self,
        projects: ProjectRepository,
        batches: HighlightBatchRepository,
        asr: AsrRepository,
        render: RenderService,
        ffmpeg: Path,
    ) -> None:
        self.projects, self.batches, self.asr, self.render, self.ffmpeg = (
            projects, batches, asr, render, ffmpeg,
        )

    def run(self, job: Job, checkpoint: dict | None, control: WorkerControl) -> JobResult:
        batch = self.batches.get(str(job.payload["batch_id"]))
        if batch is None:
            raise ValueError("高光批次不存在")
        project = self.projects.get(batch.project_id)
        if project is None:
            raise ValueError("项目不存在")
        sources = {source.id: source for source in self.projects.list_sources(batch.project_id)}
        documents = {document.source_id: document for document in self.asr.list_for_project(batch.project_id)}
        pending = [clip for clip in batch.clips if clip.status in {"queued", "failed"}]
        total = max(len(batch.clips), 1)
        config = project.config.values
        width = int(config.get("output_width", 1080))
        height = int(config.get("output_height", 1920))
        fps = int(config.get("output_fps", 30))
        self.batches.set_status(batch.id, "running")

        for clip in pending:
            if control.pause_requested or control.cancel_requested:
                self.batches.set_status(batch.id, "paused" if control.pause_requested else "cancelled")
                control.checkpoint({"batch_id": batch.id, "next_index": clip.item_index})
                return JobResult(artifacts=(batch.id,))
            self.batches.update_clip(clip.id, status="running")
            clip_job_id = f"{job.id}-{clip.item_index:03d}"
            try:
                source = sources.get(clip.source_id)
                if source is None or source.media_info is None:
                    raise ValueError("片段素材不可用")
                relative_output = PurePosixPath(project.output_relative_path) / "highlights"
                output = resolve_within_root(
                    project.root_path,
                    (relative_output / f"{clip.item_index + 1:03d}-{_safe_name(clip.title)}.mp4").as_posix(),
                )
                subtitle_path = None
                if batch.burn_subtitles:
                    document = documents.get(clip.source_id)
                    if document is not None and document.lines:
                        relative_ass = relative_output / ".blueframe-work" / clip_job_id / f"clip-{clip.item_index:03d}.ass"
                        subtitle_path = write_clip_ass(
                            document.lines,
                            resolve_within_root(project.root_path, relative_ass.as_posix()),
                            clip_start_ms=clip.start_ms,
                            clip_end_ms=clip.end_ms,
                            width=width,
                            height=height,
                        )
                artifact = self.render.render(
                    job_id=clip_job_id,
                    project_id=batch.project_id,
                    plan_id=clip.id,
                    spec=RenderSpec(
                        ffmpeg=self.ffmpeg,
                        output=output,
                        width=width,
                        height=height,
                        fps=fps,
                        inputs=(
                            RenderInput(
                                source_id=source.id,
                                path=resolve_within_root(project.root_path, source.relative_path),
                                has_audio=bool(source.media_info.get("has_audio")),
                                rotation=int(source.media_info.get("rotation") or 0),
                            ),
                        ),
                        segments=(
                            RenderSegment(
                                source_id=source.id,
                                start_ms=clip.start_ms,
                                end_ms=clip.end_ms,
                            ),
                        ),
                        subtitle_path=subtitle_path,
                    ),
                    control=_ScaledControl(control, index=clip.item_index, total=total),
                )
                if artifact.status != "completed":
                    self.batches.update_clip(clip.id, status="queued")
                    self.batches.set_status(
                        batch.id, "paused" if control.pause_requested else "cancelled"
                    )
                    return JobResult(artifacts=(batch.id,))
                self.batches.update_clip(clip.id, status="completed", output_path=artifact.published_path)
            except Exception as error:
                self.batches.update_clip(clip.id, status="failed", error_summary=_summarize(error))
            done = sum(1 for item in self.batches.get(batch.id).clips if item.status == "completed")
            control.progress(done / total * 100, "render_highlights")
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
    return (cleaned or "高光片段")[:30]


def _summarize(error: Exception) -> str:
    return " ".join(str(error).splitlines())[:300]
