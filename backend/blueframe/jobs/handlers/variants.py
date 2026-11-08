from __future__ import annotations

import os
import re
from pathlib import PurePosixPath

from blueframe.jobs.models import Job
from blueframe.projects.repository import ProjectRepository
from blueframe.rendering.service import CommandExecutor
from blueframe.security.project_paths import resolve_within_root
from blueframe.variants.graph import build_variant_command
from blueframe.variants.repository import VariantBatchRepository
from blueframe.workers.protocol import JobResult, WorkerControl


class VariantBatchHandler:
    def __init__(self, projects: ProjectRepository, batches: VariantBatchRepository, executor: CommandExecutor, ffmpeg, *, probe, assets=None) -> None:
        self.projects, self.batches, self.executor, self.ffmpeg, self.probe, self.assets = projects, batches, executor, ffmpeg, probe, assets

    def run(self, job: Job, checkpoint: dict | None, control: WorkerControl) -> JobResult:
        batch = self.batches.get(str(job.payload["batch_id"]))
        if batch is None: raise ValueError("变体批次不存在")
        project = self.projects.get(batch.project_id)
        sources = {source.id: source for source in self.projects.list_sources(batch.project_id)}
        source = sources.get(batch.source_id)
        if project is None or source is None: raise ValueError("变体源素材不存在")
        source_path = resolve_within_root(project.root_path, source.relative_path)
        pending = [item for item in batch.items if item.status in {"queued", "failed"}]
        total = max(len(batch.items), 1)
        self.batches.set_status(batch.id, "running")
        for item in pending:
            if control.pause_requested or control.cancel_requested:
                self.batches.set_status(batch.id, "paused" if control.pause_requested else "cancelled")
                control.checkpoint({"batch_id": batch.id, "next_item": item.item_index})
                return JobResult(artifacts=(batch.id,))
            self.batches.update_item(item.id, status="running")
            relative = PurePosixPath(project.output_relative_path) / "variants" / f"variant-{batch.id[:8]}-{item.item_index + 1:03d}.mp4"
            output = resolve_within_root(project.root_path, relative.as_posix())
            work = resolve_within_root(project.root_path, (PurePosixPath(project.output_relative_path) / ".blueframe-work" / job.id).as_posix())
            work.mkdir(parents=True, exist_ok=True); output.parent.mkdir(parents=True, exist_ok=True)
            temporary = work / f"variant-{item.item_index:03d}.partial.mp4"
            overlay_path = None
            if item.recipe.overlay_asset_id:
                asset = None if self.assets is None else self.assets.refresh_availability(item.recipe.overlay_asset_id)
                if asset is None or not asset.available: 
                    self.batches.update_item(item.id, status="failed", error_summary="包装图片不可用")
                    continue
                overlay_path = asset.path
            command = build_variant_command(self.ffmpeg, source_path, temporary, item.recipe, overlay_path=overlay_path)
            try:
                code = self.executor.run(command, on_output=lambda _line: control.heartbeat(), should_stop=lambda: control.pause_requested or control.cancel_requested)
                if code != 0: raise RuntimeError(f"FFmpeg exited with code {code}")
                self.probe(temporary); os.replace(temporary, output)
                self.batches.update_item(item.id, status="completed", output_path=output)
            except Exception as error:
                summary = re.sub(r"\s+", " ", str(error))[:300]
                self.batches.update_item(item.id, status="failed", error_summary=summary)
            completed = sum(current.status == "completed" for current in self.batches.get(batch.id).items)
            control.progress(completed / total * 100, "render_variants")
        final = self.batches.finish(batch.id)
        return JobResult(artifacts=(final.id,))
