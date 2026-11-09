from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from blueframe.security.project_paths import resolve_within_root


class LegacyPathRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    root_id: str = Field(min_length=1)
    relative_path: str = Field(min_length=1)


class ConfirmLegacyImportRequest(LegacyPathRequest):
    expected_source_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    confirmed: bool


def build_legacy_router(auth, roots, importer) -> APIRouter:
    router = APIRouter(prefix="/legacy-import", dependencies=[Depends(auth)])

    def path(request):
        try: return resolve_within_root(roots.root(request.root_id), request.relative_path)
        except (KeyError, ValueError) as error:
            raise HTTPException(400, detail={"code": "invalid_legacy_path", "message": "旧数据库路径未授权"}) from error

    @router.post("/preview")
    def preview(request: LegacyPathRequest):
        try: return importer.preview(path(request)).model_dump(mode="json")
        except (OSError, ValueError) as error: raise HTTPException(400, detail={"code": "legacy_preview_failed", "message": str(error)}) from error

    @router.post("/confirm")
    def confirm(request: ConfirmLegacyImportRequest):
        try:
            return importer.import_confirmed(
                path(request), expected_source_hash=request.expected_source_hash, confirmed=request.confirmed,
            ).model_dump(mode="json")
        except (OSError, ValueError) as error: raise HTTPException(400, detail={"code": "legacy_import_failed", "message": str(error)}) from error

    return router
