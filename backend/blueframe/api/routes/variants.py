from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field

from blueframe.variants.models import generate_recipe


class CreateVariantBatchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source_id: str = Field(min_length=1)
    count: int = Field(ge=1, le=50)
    seed: int = Field(ge=0, le=2**63 - 1)
    width: int = Field(ge=320, le=3840)
    height: int = Field(ge=320, le=3840)
    overlay_asset_id: str | None = None
    idempotency_key: str = Field(min_length=1, max_length=200)


class RetryVariantBatchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    idempotency_key: str = Field(min_length=1, max_length=200)


def build_variants_router(auth, projects, batches, jobs, account_service, assets=None) -> APIRouter:
    router = APIRouter(prefix="/projects", dependencies=[Depends(auth)])

    def require_project(project_id: str):
        project = projects.get(project_id)
        if project is None: raise HTTPException(404, detail={"code": "project_not_found", "message": "项目不存在"})
        return project

    @router.get("/{project_id}/variant-batches")
    def list_batches(project_id: str):
        require_project(project_id)
        return [_payload(batch) for batch in batches.list_for_project(project_id)]

    @router.post("/{project_id}/variant-batches", status_code=status.HTTP_202_ACCEPTED)
    def create_batch(project_id: str, request: CreateVariantBatchRequest):
        require_project(project_id)
        source = projects.get_source(request.source_id)
        if source is None or source.project_id != project_id:
            raise HTTPException(400, detail={"code": "invalid_variant_source", "message": "变体源素材无效"})
        if request.width % 2 or request.height % 2:
            raise HTTPException(400, detail={"code": "invalid_variant_dimensions", "message": "输出尺寸必须为偶数"})
        if request.overlay_asset_id:
            asset = None if assets is None else assets.get(request.overlay_asset_id)
            if asset is None or not asset.available or asset.asset_type.value != "image":
                raise HTTPException(400, detail={"code": "invalid_overlay_asset", "message": "包装图片不存在或不可用"})
        recipes = tuple(generate_recipe(
            seed=request.seed, index=index, width=request.width, height=request.height,
            overlay_asset_id=request.overlay_asset_id,
        ) for index in range(request.count))
        batch = batches.create(project_id=project_id, source_id=request.source_id, recipes=recipes)
        job = jobs.create("render_variant_batch", {"batch_id": batch.id, "project_id": project_id}, request.idempotency_key)
        return {"batch": _payload(batch), "job": job.model_dump(mode="json")}

    @router.post("/{project_id}/variant-batches/{batch_id}/retry", status_code=status.HTTP_202_ACCEPTED)
    def retry_batch(project_id: str, batch_id: str, request: RetryVariantBatchRequest):
        require_project(project_id); batch = batches.get(batch_id)
        if batch is None or batch.project_id != project_id:
            raise HTTPException(404, detail={"code": "variant_batch_not_found", "message": "变体批次不存在"})
        retried = batches.retry_failed(batch_id)
        job = jobs.create("render_variant_batch", {"batch_id": batch_id, "project_id": project_id}, request.idempotency_key)
        return {"batch": _payload(retried), "job": job.model_dump(mode="json")}

    return router


def _payload(batch) -> dict:
    return {
        "id": batch.id, "project_id": batch.project_id, "source_id": batch.source_id,
        "status": batch.status, "created_at": batch.created_at.isoformat(),
        "items": [{
            "id": item.id, "item_index": item.item_index, "status": item.status,
            "recipe": item.recipe.model_dump(mode="json"),
            "output_filename": None if item.output_path is None else item.output_path.name,
            "error_summary": item.error_summary,
        } for item in batch.items],
    }
