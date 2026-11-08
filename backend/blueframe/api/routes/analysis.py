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
            return analyses.accept(
                project_id=project_id, version=version
            ).model_dump(mode="json")
        except KeyError as error:
            raise HTTPException(
                404,
                detail={"code": "analysis_not_found", "message": "分析版本不存在"},
            ) from error

    return router
