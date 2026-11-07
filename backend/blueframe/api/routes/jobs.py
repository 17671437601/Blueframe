from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field

from blueframe.jobs.repository import JobRepository
from blueframe.jobs.state_machine import InvalidJobTransition


class CreateJobRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    job_type: str = Field(min_length=1)
    payload: dict
    idempotency_key: str = Field(min_length=1)
    priority: int = 0


def build_jobs_router(auth, repository: JobRepository, account_service) -> APIRouter:
    router = APIRouter(prefix="/jobs", dependencies=[Depends(auth)])

    @router.get("")
    def list_jobs():
        return [job.model_dump(mode="json") for job in repository.list()]

    @router.post("", status_code=status.HTTP_201_CREATED)
    def create_job(request: CreateJobRequest):
        access = account_service.evaluate_access(datetime.now(UTC))
        if access.mode == "readonly" and not request.job_type.startswith("export"):
            raise HTTPException(403, detail={"code": "account_readonly", "message": "账号离线宽限已结束"})
        return repository.create(
            request.job_type, request.payload, request.idempotency_key, priority=request.priority
        ).model_dump(mode="json")

    @router.get("/{job_id}")
    def get_job(job_id: str):
        job = repository.get(job_id)
        if job is None:
            raise HTTPException(404, detail={"code": "job_not_found", "message": "任务不存在"})
        return job.model_dump(mode="json")

    def control(operation, job_id: str):
        try:
            return operation(job_id).model_dump(mode="json")
        except KeyError:
            raise HTTPException(404, detail={"code": "job_not_found", "message": "任务不存在"})
        except InvalidJobTransition as error:
            raise HTTPException(409, detail={"code": "invalid_job_transition", "message": str(error)})

    @router.post("/{job_id}/pause")
    def pause(job_id: str):
        return control(repository.request_pause, job_id)

    @router.post("/{job_id}/resume")
    def resume(job_id: str):
        return control(repository.resume, job_id)

    @router.post("/{job_id}/cancel")
    def cancel(job_id: str):
        return control(repository.cancel, job_id)

    return router
