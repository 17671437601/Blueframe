from datetime import UTC, datetime

from fastapi import APIRouter, Depends


def build_account_router(auth, account_service) -> APIRouter:
    router = APIRouter(prefix="/account", dependencies=[Depends(auth)])

    @router.get("/access")
    def access():
        return account_service.evaluate_access(datetime.now(UTC))

    return router
