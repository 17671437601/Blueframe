from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from blueframe.providers.volcengine.config_service import ArkConfigService, ArkConfigStatus


class UpdateArkConfigRequest(BaseModel):
    model: str = Field(min_length=1, max_length=200)
    api_key: str | None = Field(default=None, min_length=1, max_length=4096)


def build_provider_router(auth, service: ArkConfigService) -> APIRouter:
    router = APIRouter(prefix="/providers", dependencies=[Depends(auth)])

    @router.get("/volcengine", response_model=ArkConfigStatus)
    def get_volcengine_config() -> ArkConfigStatus:
        return service.status()

    @router.put("/volcengine", response_model=ArkConfigStatus)
    def update_volcengine_config(request: UpdateArkConfigRequest) -> ArkConfigStatus:
        try:
            return service.configure(model=request.model, api_key=request.api_key)
        except ValueError as error:
            raise HTTPException(400, detail=str(error)) from error

    return router
