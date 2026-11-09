from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, status


def build_diagnostics_router(auth, service, export_dir) -> APIRouter:
    router = APIRouter(prefix="/diagnostics", dependencies=[Depends(auth)])

    @router.get("/summary")
    def summary(): return service.summary()

    @router.post("/export", status_code=status.HTTP_201_CREATED)
    def export():
        timestamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
        filename = f"blueframe-diagnostics-{timestamp}.zip"
        service.export(export_dir / filename, system={"app_version": "0.1.0"})
        return {"filename": filename}

    return router
