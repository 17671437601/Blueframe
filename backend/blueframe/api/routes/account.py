from datetime import UTC, datetime

from fastapi import APIRouter, Depends


def build_account_router(auth, account_service) -> APIRouter:
    router = APIRouter(prefix="/account", dependencies=[Depends(auth)])

    @router.get("/access")
    def access():
        evaluated = account_service.evaluate_access(datetime.now(UTC))
        payload = evaluated.model_dump(exclude={"grace_remaining"})
        payload["grace_remaining_seconds"] = (
            None
            if evaluated.grace_remaining is None
            else int(evaluated.grace_remaining.total_seconds())
        )
        return payload

    return router
