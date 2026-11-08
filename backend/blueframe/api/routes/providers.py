from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from blueframe.providers.volcengine.config_service import ArkConfigService, ArkConfigStatus
from blueframe.providers.volcengine.tts import VolcengineTtsConfigService, VolcengineTtsConfigStatus


class UpdateArkConfigRequest(BaseModel):
    model: str = Field(min_length=1, max_length=200)
    api_key: str | None = Field(default=None, min_length=1, max_length=4096)


class UpdateTtsConfigRequest(BaseModel):
    default_voice: str = Field(min_length=1, max_length=200)
    api_key: str | None = Field(default=None, min_length=1, max_length=4096)


def build_provider_router(auth, service: ArkConfigService | None, tts_service: VolcengineTtsConfigService | None = None) -> APIRouter:
    router = APIRouter(prefix="/providers", dependencies=[Depends(auth)])

    if service is not None:
        @router.get("/volcengine", response_model=ArkConfigStatus)
        def get_volcengine_config() -> ArkConfigStatus:
            return service.status()

        @router.put("/volcengine", response_model=ArkConfigStatus)
        def update_volcengine_config(request: UpdateArkConfigRequest) -> ArkConfigStatus:
            try:
                return service.configure(model=request.model, api_key=request.api_key)
            except ValueError as error:
                raise HTTPException(400, detail=str(error)) from error

    if tts_service is not None:
        @router.get("/volcengine-tts", response_model=VolcengineTtsConfigStatus)
        def get_tts_config() -> VolcengineTtsConfigStatus:
            return tts_service.status()

        @router.put("/volcengine-tts", response_model=VolcengineTtsConfigStatus)
        def update_tts_config(request: UpdateTtsConfigRequest) -> VolcengineTtsConfigStatus:
            try:
                return tts_service.configure(default_voice=request.default_voice, api_key=request.api_key)
            except ValueError as error:
                raise HTTPException(400, detail=str(error)) from error

    return router
