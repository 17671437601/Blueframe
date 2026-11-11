from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field

from blueframe.highlights.planner import build_highlight_clips


class CreateHighlightBatchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    analysis_version_id: str | None = Field(default=None, min_length=1, max_length=36)
    target_count: int = Field(ge=1, le=60)
    min_duration_ms: int = Field(ge=3000, le=180_000)
    max_duration_ms: int = Field(ge=5000, le=180_000)
    burn_subtitles: bool = True
    idempotency_key: str = Field(min_length=1, max_length=200)


class RetryHighlightBatchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    idempotency_key: str = Field(min_length=1, max_length=200)


def build_highlight_router(auth, projects, analyses, batches, jobs, account_service, asr=None) -> APIRouter:
    router = APIRouter(prefix="/projects", dependencies=[Depends(auth)])

    def require_project(project_id: str):
        project = projects.get(project_id)
        if project is None:
            raise HTTPException(404, detail={"code": "project_not_found", "message": "项目不存在"})
        return project

    def writable() -> None:
        if account_service.evaluate_access(datetime.now(UTC)).mode == "readonly":
            raise HTTPException(403, detail={"code": "account_readonly", "message": "当前账号仅允许查看和导出"})

    @router.get("/{project_id}/highlight-batches")
    def list_batches(project_id: str):
        require_project(project_id)
        return [_payload(batch) for batch in batches.list_for_project(project_id)]

    @router.post("/{project_id}/highlight-batches", status_code=status.HTTP_202_ACCEPTED)
    def create_batch(project_id: str, request: CreateHighlightBatchRequest):
        require_project(project_id)
        writable()
        if request.max_duration_ms <= request.min_duration_ms:
            raise HTTPException(
                400,
                detail={"code": "invalid_clip_duration", "message": "最长时长必须大于最短时长"},
            )
        version = _resolve_analysis(analyses, project_id, request.analysis_version_id)
        if version is None:
            raise HTTPException(
                409,
                detail={"code": "analysis_required", "message": "请先完成剧情分析并接受一个版本"},
            )
        lines_by_source = {}
        if asr is not None:
            lines_by_source = {
                document.source_id: document.lines for document in asr.list_for_project(project_id)
            }
        specs = build_highlight_clips(
            version.analysis,
            projects.list_sources(project_id),
            target_count=request.target_count,
            min_duration_ms=request.min_duration_ms,
            max_duration_ms=request.max_duration_ms,
            lines_by_source=lines_by_source,
        )
        if not specs:
            raise HTTPException(
                409,
                detail={
                    "code": "no_highlight_candidates",
                    "message": "分析结果中没有可用的高能点，请重新分析或放宽时长范围",
                },
            )
        batch = batches.create(
            project_id=project_id,
            analysis_version_id=version.id,
            specs=specs,
            target_count=request.target_count,
            min_duration_ms=request.min_duration_ms,
            max_duration_ms=request.max_duration_ms,
            burn_subtitles=request.burn_subtitles,
        )
        job = jobs.create(
            "render_highlights",
            {"batch_id": batch.id, "project_id": project_id},
            request.idempotency_key,
        )
        return {"batch": _payload(batch), "job": job.model_dump(mode="json")}

    @router.post(
        "/{project_id}/highlight-batches/{batch_id}/retry",
        status_code=status.HTTP_202_ACCEPTED,
    )
    def retry_batch(project_id: str, batch_id: str, request: RetryHighlightBatchRequest):
        require_project(project_id)
        writable()
        batch = batches.get(batch_id)
        if batch is None or batch.project_id != project_id:
            raise HTTPException(
                404, detail={"code": "highlight_batch_not_found", "message": "高光批次不存在"}
            )
        retried = batches.retry_failed(batch_id)
        job = jobs.create(
            "render_highlights",
            {"batch_id": batch_id, "project_id": project_id},
            request.idempotency_key,
        )
        return {"batch": _payload(retried), "job": job.model_dump(mode="json")}

    return router


def _resolve_analysis(analyses, project_id: str, analysis_version_id: str | None):
    if analysis_version_id is not None:
        version = analyses.get(analysis_version_id)
        if version is None or version.project_id != project_id:
            raise HTTPException(
                400, detail={"code": "invalid_analysis_version", "message": "分析版本不存在"}
            )
        return version
    candidates = analyses.list_for_project(project_id)
    accepted = next((item for item in candidates if item.accepted), None)
    return accepted or (candidates[0] if candidates else None)


def _payload(batch) -> dict:
    return {
        "id": batch.id,
        "project_id": batch.project_id,
        "analysis_version_id": batch.analysis_version_id,
        "status": batch.status,
        "target_count": batch.target_count,
        "min_duration_ms": batch.min_duration_ms,
        "max_duration_ms": batch.max_duration_ms,
        "burn_subtitles": batch.burn_subtitles,
        "created_at": batch.created_at.isoformat(),
        "clips": [
            {
                "id": clip.id,
                "item_index": clip.item_index,
                "title": clip.title,
                "reason": clip.reason,
                "score": clip.score,
                "start_ms": clip.start_ms,
                "end_ms": clip.end_ms,
                "duration_ms": clip.duration_ms,
                "status": clip.status,
                "output_filename": None if clip.output_path is None else clip.output_path.name,
                "error_summary": clip.error_summary,
            }
            for clip in batch.clips
        ],
    }
