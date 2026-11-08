from __future__ import annotations

import hashlib
import json
import os
import subprocess
from pathlib import Path
from typing import Callable, Protocol

from blueframe.rendering.artifacts import RenderArtifact, RenderArtifactRepository
from blueframe.rendering.graph import RenderSpec, build_render_commands
from blueframe.rendering.progress import FfmpegProgressParser
from blueframe.workers.protocol import WorkerControl


class CommandExecutor(Protocol):
    def run(self, command: list[str], *, on_output: Callable[[str], None], should_stop: Callable[[], bool]) -> int: ...


class FfmpegExecutor:
    def run(self, command, *, on_output, should_stop) -> int:
        process = subprocess.Popen(
            command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, encoding="utf-8", errors="replace", shell=False,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        assert process.stdout is not None
        for line in process.stdout:
            on_output(line)
            if should_stop():
                process.terminate()
                break
        return process.wait()


class RenderService:
    def __init__(
        self, repository: RenderArtifactRepository, *, executor: CommandExecutor,
        probe: Callable[[Path], object], hardware_encoder: str | None = "h264_nvenc",
    ) -> None:
        self.repository = repository
        self.executor = executor
        self.probe = probe
        self.hardware_encoder = hardware_encoder

    def render(
        self, *, job_id: str, project_id: str, plan_id: str,
        spec: RenderSpec, control: WorkerControl,
    ) -> RenderArtifact:
        spec_hash = hashlib.sha256(
            spec.model_dump_json().encode("utf-8")
        ).hexdigest()
        reusable = self.repository.find_completed(project_id, plan_id, spec_hash)
        if reusable and reusable.published_path and reusable.published_path.is_file():
            self.probe(reusable.published_path)
            return reusable

        work_dir = spec.output.parent / ".blueframe-work" / job_id
        work_dir.mkdir(parents=True, exist_ok=True)
        temporary_output = work_dir / "render.partial.mp4"
        artifact = self.repository.start(
            job_id=job_id, project_id=project_id, plan_id=plan_id,
            spec_hash=spec_hash, working_path=temporary_output,
        )
        if control.pause_requested or control.cancel_requested:
            control.checkpoint({"stage": "waiting_to_render", "artifact_id": artifact.id})
            return self.repository.update(
                artifact.id, status="paused" if control.pause_requested else "cancelled"
            )

        working_spec = spec.model_copy(update={"output": temporary_output})
        primary, fallback = build_render_commands(
            working_spec, hardware_encoder=self.hardware_encoder
        )
        parser = FfmpegProgressParser(
            duration_ms=sum(item.end_ms - item.start_ms for item in spec.segments)
        )

        def on_output(data: str) -> None:
            for value in parser.feed(data):
                control.progress(value * 0.9, "render_media")
            control.heartbeat()

        should_stop = lambda: control.pause_requested or control.cancel_requested
        code = self.executor.run(primary, on_output=on_output, should_stop=should_stop)
        if code != 0 and not should_stop() and primary != fallback:
            code = self.executor.run(fallback, on_output=on_output, should_stop=should_stop)
        if should_stop():
            control.checkpoint({"stage": "render_interrupted", "artifact_id": artifact.id})
            return self.repository.update(
                artifact.id, status="paused" if control.pause_requested else "cancelled"
            )
        if code != 0:
            self.repository.update(artifact.id, status="failed")
            raise RuntimeError(f"FFmpeg exited with code {code}")

        self.probe(temporary_output)
        checksum = _sha256(temporary_output)
        spec.output.parent.mkdir(parents=True, exist_ok=True)
        os.replace(temporary_output, spec.output)
        manifest = spec.output.with_suffix(".manifest.json")
        manifest_temp = manifest.with_suffix(".json.tmp")
        manifest_temp.write_text(json.dumps({
            "artifact_id": artifact.id, "plan_id": plan_id, "sha256": checksum,
            "output": spec.output.name,
        }, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(manifest_temp, manifest)
        control.progress(100, "publish_media")
        control.checkpoint({"stage": "published", "artifact_id": artifact.id, "output": spec.output.name})
        return self.repository.update(
            artifact.id, status="completed", published_path=spec.output, checksum=checksum
        )


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()
