from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field

from blueframe.editing.models import EditPlanDraft, EditSegment, PlanKind
from blueframe.story.planner import MIN_OUTPUT_MS, build_story_plans


class CreateStoryBatchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    analysis_version_id: str | None = Field(default=None, min_length=1, max_length=36)
    target_count: int = Field(ge=1, le=50)
    min_duration_ms: int = Field(ge=MIN_OUTPUT_MS, le=3_600_000)
    max_duration_ms: int = Field(ge=MIN_OUTPUT_MS, le=3_600_000)
    burn_subtitles: bool = True
    idempotency_key: str = Field(min_length=1, max_length=200)


class RetryStoryBatchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    idempotency_key: str = Field(min_length=1, max_length=200)


def build_story_router(
    auth, projects, analyses, batches, plans, jobs, account_service, asr=None
) -> APIRouter:
    router = APIRouter(prefix="/projects", dependencies=[Depends(auth)])

    def require_project(project_id: str):
        project = projects.get(project_id)
        if project is None:
            raise HTTPException(404, detail={"code": "project_not_found", "message": "项目不存在"})
        return project

    def writable() -> None:
        if account_service.evaluate_access(datetime.now(UTC)).mode == "readonly":
            raise HTTPException(403, detail={"code": "account_readonly", "message": "当前账号仅允许查看和导出"})

    @router.get("/{project_id}/story-batches")
    def list_batches(project_id: str):
        require_project(project_id)
        return [_payload(batch, plans) for batch in batches.list_for_project(project_id)]

    @router.post("/{project_id}/story-batches", status_code=status.HTTP_202_ACCEPTED)
    def create_batch(project_id: str, request: CreateStoryBatchRequest):
        require_project(project_id)
        writable()
        if request.max_duration_ms <= request.min_duration_ms:
            raise HTTPException(
                400,
                detail={"code": "invalid_duration_window", "message": "最长时长必须大于最短时长"},
            )
        version = _resolve_analysis(analyses, project_id, request.analysis_version_id)
        if version is None:
            raise HTTPException(
                409,
                detail={"code": "analysis_required", "message": "请先完成剧情分析并接受一个版本"},
            )
        sources = projects.list_sources(project_id)
        total_duration = sum(int((source.media_info or {}).get("duration_ms") or 0) for source in sources)
        if total_duration < request.min_duration_ms:
            raise HTTPException(
                409,
                detail={
                    "code": "insufficient_media",
                    "message": "素材总时长不足以生成目标时长的成片，请缩短时长或补充剧集",
                },
            )
        lines_by_source = {}
        if asr is not None:
            lines_by_source = {
                document.source_id: document.lines for document in asr.list_for_project(project_id)
            }
        try:
            specs = build_story_plans(
                version.analysis,
                sources,
                target_count=request.target_count,
                min_duration_ms=request.min_duration_ms,
                max_duration_ms=request.max_duration_ms,
                lines_by_source=lines_by_source,
            )
        except ValueError as error:
            raise HTTPException(
                409,
                detail={"code": "no_story_candidates", "message": str(error)},
            ) from error
        if not specs:
            raise HTTPException(
                409,
                detail={
                    "code": "no_story_candidates",
                    "message": "分析结果中没有可用的主线片段，请重新分析",
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
        durations = {source.id: int((source.media_info or {}).get("duration_ms") or 0) for source in sources}
        for item, spec in zip(batch.items, specs, strict=False):
            plan = plans.save(
                project_id,
                EditPlanDraft(
                    title=spec.title,
                    kind=PlanKind.STORY,
                    target_duration_ms=spec.target_duration_ms,
                    segments=tuple(
                        EditSegment(
                            source_id=segment.source_id,
                            source_start_ms=segment.start_ms,
                            source_end_ms=segment.end_ms,
                            source_duration_ms=max(durations.get(segment.source_id, 0), segment.end_ms),
                        )
                        for segment in spec.segments
                    ),
                ),
                idempotency_key=f"story:{batch.id}:{item.item_index}",
            )
            batches.attach_plan(item.id, plan.id)
        job = jobs.create(
            "render_story_batch",
            {"batch_id": batch.id, "project_id": project_id},
            request.idempotency_key,
        )
        return {"batch": _payload(batches.get(batch.id), plans), "job": job.model_dump(mode="json")}

    @router.post(
        "/{project_id}/story-batches/{batch_id}/retry",
        status_code=status.HTTP_202_ACCEPTED,
    )
    def retry_batch(project_id: str, batch_id: str, request: RetryStoryBatchRequest):
        require_project(project_id)
        writable()
        batch = batches.get(batch_id)
        if batch is None or batch.project_id != project_id:
            raise HTTPException(
                404, detail={"code": "story_batch_not_found", "message": "主线成片批次不存在"}
            )
        retried = batches.retry_failed(batch_id)
        job = jobs.create(
            "render_story_batch",
            {"batch_id": batch_id, "project_id": project_id},
            request.idempotency_key,
        )
        return {"batch": _payload(retried, plans), "job": job.model_dump(mode="json")}

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


def _payload(batch, plans) -> dict:
    items = []
    for item in batch.items:
        plan = None if item.plan_id is None else plans.get(item.plan_id)
        items.append(
            {
                "id": item.id,
                "item_index": item.item_index,
                "title": item.title,
                "target_duration_ms": item.target_duration_ms,
                "duration_ms": 0 if plan is None else plan.duration_ms,
                "status": item.status,
                "output_filename": None if item.output_path is None else item.output_path.name,
                "error_summary": item.error_summary,
            }
        )
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
        "items": items,
    }
