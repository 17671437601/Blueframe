from __future__ import annotations

from blueframe.asr.repository import AsrRepository
from blueframe.commentary.service import CommentaryService
from blueframe.jobs.models import Job
from blueframe.workers.protocol import JobResult, WorkerControl


class ProjectCommentaryHandler:
    def __init__(self, asr: AsrRepository, commentary: CommentaryService) -> None:
        self.asr, self.commentary = asr, commentary

    def run(self, job: Job, checkpoint: dict | None, control: WorkerControl) -> JobResult:
        project_id = str(job.payload["project_id"])
        documents = tuple(self.asr.list_for_project(project_id))
        script_id = job.payload.get("script_id")
        if script_id is None:
            result = self.commentary.generate(
                project_id=project_id, documents=documents, voice=str(job.payload["voice"]),
            )
        else:
            base = self.commentary.repository.get(str(script_id))
            if base is None or base.project_id != project_id:
                raise KeyError("commentary script not found")
            result = self.commentary.regenerate_sentence(
                base=base, sentence_index=int(job.payload["sentence_index"]), documents=documents,
            )
        control.progress(100, "generate_commentary")
        return JobResult(artifacts=(result.id,))
