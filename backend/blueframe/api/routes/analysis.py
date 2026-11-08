from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field


class StartAnalysisRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    consent_to_send_transcript: bool
    idempotency_key: str = Field(min_length=1, max_length=200)


def build_analysis_router(
    auth,
    projects,
    jobs,
    analyses,
    account_service,
    provider_config_service,
    edit_plan_repository=None,
) -> APIRouter:
    router = APIRouter(prefix="/projects", dependencies=[Depends(auth)])

    def require_project(project_id: str):
        project = projects.get(project_id)
        if project is None:
            raise HTTPException(
                404, detail={"code": "project_not_found", "message": "项目不存在"}
            )
        return project

    @router.get("/{project_id}/analyses")
    def list_analyses(project_id: str):
        require_project(project_id)
        return [
            item.model_dump(mode="json")
            for item in analyses.list_for_project(project_id)
        ]

    @router.post(
        "/{project_id}/analyze", status_code=status.HTTP_202_ACCEPTED
    )
    def start_analysis(project_id: str, request: StartAnalysisRequest):
        require_project(project_id)
        if not request.consent_to_send_transcript:
            raise HTTPException(
                400,
                detail={
                    "code": "transcript_consent_required",
                    "message": "需要明确同意发送字幕文本",
                },
            )
        provider_status = provider_config_service.status()
        if not provider_status.configured:
            raise HTTPException(
                409,
                detail={
                    "code": "provider_not_configured",
                    "message": "请先在设置中配置火山引擎",
                },
            )
        access = account_service.evaluate_access(
            datetime.now(UTC), provider_available=True
        )
        if not access.remote_ai:
            raise HTTPException(
                403,
                detail={"code": "remote_ai_denied", "message": "当前账号不能使用远程 AI"},
            )
        job = jobs.create(
            "analyze_project",
            {"project_id": project_id, "transcript_consent": True},
            request.idempotency_key,
        )
        return job.model_dump(mode="json")

    @router.post("/{project_id}/analyses/{version}/accept")
    def accept_analysis(project_id: str, version: int):
        require_project(project_id)
        try:
            accepted = analyses.accept(
                project_id=project_id, version=version
            )
            if edit_plan_repository is not None and not edit_plan_repository.list_for_project(project_id):
                _create_initial_plan(
                    project_id, accepted, projects.list_sources(project_id), edit_plan_repository
                )
            return accepted.model_dump(mode="json")
        except KeyError as error:
            raise HTTPException(
                404,
                detail={"code": "analysis_not_found", "message": "分析版本不存在"},
            ) from error

    return router


def _create_initial_plan(project_id, version, sources, plans) -> None:
    from blueframe.editing.models import EditPlanDraft, EditSegment, PlanKind

    ranges = []
    if version.analysis.edit_candidates:
        candidate = version.analysis.edit_candidates[0]
        ranges = list(candidate.segments)
        title = candidate.title
    else:
        ranges = [(item.start_ms, item.end_ms) for item in version.analysis.explosions]
        title = "AI 高光方案"
    if not ranges:
        return
    source_ranges = []
    offset = 0
    for source in sources:
        duration = int((source.media_info or {}).get("duration_ms") or 0)
        if duration > 0:
            source_ranges.append((source, offset, offset + duration, duration))
            offset += duration
    segments = []
    for global_start, global_end in ranges:
        for source, source_start, source_end, duration in source_ranges:
            overlap_start = max(global_start, source_start)
            overlap_end = min(global_end, source_end)
            if overlap_end - overlap_start >= 500:
                segments.append(EditSegment(
                    source_id=source.id,
                    source_start_ms=overlap_start - source_start,
                    source_end_ms=overlap_end - source_start,
                    source_duration_ms=duration,
                ))
    if not segments:
        return
    plans.save(
        project_id,
        EditPlanDraft(
            title=title, kind=PlanKind.HIGHLIGHT,
            target_duration_ms=sum(item.duration_ms for item in segments),
            segments=tuple(segments),
        ),
        idempotency_key=f"analysis:{version.id}:candidate:0",
    )
