from __future__ import annotations

from blueframe.asr.models import AsrLine, AsrStatus
from blueframe.asr.repository import AsrRepository
from blueframe.drama.analysis_service import AnalysisService
from blueframe.jobs.models import Job
from blueframe.workers.protocol import JobResult, WorkerControl


class ProjectAnalysisHandler:
    def __init__(self, asr: AsrRepository, analysis: AnalysisService) -> None:
        self.asr = asr
        self.analysis = analysis

    def run(self, job: Job, checkpoint: dict | None, control: WorkerControl) -> JobResult:
        project_id = str(job.payload["project_id"])
        documents = [
            document
            for document in self.asr.list_for_project(project_id)
            if document.status is AsrStatus.COMPLETED
        ]
        lines: list[AsrLine] = []
        offset = 0
        for document in documents:
            for line in document.lines:
                lines.append(
                    AsrLine(
                        index=len(lines), start_ms=offset + line.start_ms,
                        end_ms=offset + line.end_ms, text=line.text,
                    )
                )
            offset += document.duration_ms
        result = self.analysis.analyze(
            project_id=project_id,
            lines=tuple(lines),
            media_duration_ms=offset,
            checkpoint=checkpoint,
            control=control,
        )
        return JobResult(artifacts=() if result is None else (result.version.id,))
