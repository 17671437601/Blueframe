from fastapi import APIRouter, Depends


def build_system_router(auth) -> APIRouter:
    router = APIRouter(prefix="/system", dependencies=[Depends(auth)])

    @router.get("/status")
    def status() -> dict[str, str]:
        return {"status": "ok"}

    return router
