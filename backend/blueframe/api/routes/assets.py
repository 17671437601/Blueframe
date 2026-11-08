from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field

from blueframe.assets.models import StorageOwnership
from blueframe.security.project_paths import resolve_within_root


class ImportAssetsRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    root_id: str = Field(min_length=1)
    relative_paths: list[str] = Field(min_length=1, max_length=200)
    origin: str = Field(min_length=1, max_length=500)
    license_name: str = Field(min_length=1, max_length=500)
    ownership: StorageOwnership = StorageOwnership.LINKED


def build_assets_router(auth, roots, repository, scanner) -> APIRouter:
    router = APIRouter(prefix="/assets", dependencies=[Depends(auth)])

    @router.get("")
    def list_assets(asset_type: str | None = None):
        assets = repository.list(asset_type=asset_type)
        refreshed = [repository.refresh_availability(asset.id) for asset in assets]
        return [_payload(asset) for asset in refreshed]

    @router.post("", status_code=status.HTTP_201_CREATED)
    def import_assets(request: ImportAssetsRequest):
        try: root = roots.root(request.root_id)
        except KeyError as error: raise HTTPException(400, detail={"code": "invalid_asset_root", "message": "素材目录未授权"}) from error
        imported, errors = [], []
        for relative in request.relative_paths:
            try:
                path = resolve_within_root(root, relative)
                draft = scanner.scan(path, origin=request.origin, license_name=request.license_name, ownership=request.ownership)
                imported.append(_payload(repository.save(draft)))
            except (OSError, ValueError) as error:
                errors.append({"relative_path": relative, "message": str(error)})
        if not imported:
            raise HTTPException(400, detail={"code": "asset_import_failed", "message": "没有可导入的素材", "errors": errors})
        return {"items": imported, "errors": errors}

    return router


def _payload(asset) -> dict:
    return {
        "id": asset.id, "sha256": asset.sha256, "asset_type": asset.asset_type.value,
        "filename": str(asset.metadata.get("filename") or asset.path.name),
        "origin": asset.origin, "license_name": asset.license_name,
        "ownership": asset.ownership.value, "available": asset.available,
        "metadata": asset.metadata, "created_at": asset.created_at.isoformat(),
    }
