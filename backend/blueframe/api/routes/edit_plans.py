from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field

from blueframe.editing.models import EditPlanDraft, EditSegment, PlanKind


class SaveEditPlanRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str = Field(min_length=1, max_length=200)
    kind: PlanKind
    target_duration_ms: int = Field(gt=0)
    segments: tuple[EditSegment, ...] = Field(min_length=1)
    idempotency_key: str = Field(min_length=1, max_length=200)


def build_edit_plan_router(auth, projects, plans, jobs, account_service) -> APIRouter:
    router = APIRouter(prefix="/projects", dependencies=[Depends(auth)])

    def project(project_id: str):
        found = projects.get(project_id)
        if found is None:
            raise HTTPException(404, detail={"code": "project_not_found", "message": "项目不存在"})
        return found

    def writable() -> None:
        if account_service.evaluate_access(datetime.now(UTC)).mode == "readonly":
            raise HTTPException(403, detail={"code": "account_readonly", "message": "当前账号仅允许查看和导出"})

    @router.get("/{project_id}/edit-plans")
    def list_plans(project_id: str):
        project(project_id)
        return [item.model_dump(mode="json") for item in plans.list_for_project(project_id)]

    @router.post("/{project_id}/edit-plans", status_code=status.HTTP_201_CREATED)
    def save_plan(project_id: str, request: SaveEditPlanRequest):
        project(project_id); writable()
        draft = EditPlanDraft(
            title=request.title, kind=request.kind,
            target_duration_ms=request.target_duration_ms, segments=request.segments,
        )
        return plans.save(
            project_id, draft, idempotency_key=request.idempotency_key
        ).model_dump(mode="json")

    @router.post("/{project_id}/edit-plans/{plan_id}/render", status_code=status.HTTP_202_ACCEPTED)
    def render_plan(project_id: str, plan_id: str):
        project(project_id); writable()
        plan = plans.get(plan_id)
        if plan is None or plan.project_id != project_id:
            raise HTTPException(404, detail={"code": "edit_plan_not_found", "message": "剪辑方案不存在"})
        return jobs.create(
            "render_edit_plan", {"project_id": project_id, "plan_id": plan_id},
            f"render:{project_id}:{plan_id}",
        ).model_dump(mode="json")

    return router
