from __future__ import annotations

from datetime import datetime, timedelta
from typing import Literal, Protocol

from pydantic import BaseModel, ConfigDict

from blueframe.auth.entitlement_cache import EntitlementSnapshot


class EntitlementCache(Protocol):
    last_evaluated_at: datetime | None
    def get_snapshot(self) -> EntitlementSnapshot | None: ...
    def update_last_evaluated(self, value: datetime) -> None: ...


class AccountAccess(BaseModel):
    model_config = ConfigDict(frozen=True)
    mode: Literal["online", "grace", "readonly"]
    local_processing: bool
    remote_ai: bool
    export: bool
    grace_remaining: timedelta | None = None


class AccountService:
    GRACE = timedelta(hours=72)

    def __init__(self, cache: EntitlementCache) -> None:
        self.cache = cache

    def evaluate_access(self, now: datetime, provider_available: bool = False) -> AccountAccess:
        effective_now = max(now, self.cache.last_evaluated_at or now)
        self.cache.update_last_evaluated(effective_now)
        snapshot = self.cache.get_snapshot()
        if snapshot is None or not snapshot.is_trusted:
            return AccountAccess(mode="readonly", local_processing=False, remote_ai=False, export=True)
        age = effective_now - snapshot.verified_at
        token_valid = effective_now < snapshot.token_expires_at
        entitlement_valid = snapshot.entitlements.valid_from <= effective_now < snapshot.entitlements.valid_until
        if provider_available and token_valid and entitlement_valid:
            return AccountAccess(mode="online", local_processing=True, remote_ai=True, export=True)
        if timedelta(0) <= age < self.GRACE and entitlement_valid:
            return AccountAccess(
                mode="grace", local_processing=True, remote_ai=token_valid,
                export=True, grace_remaining=self.GRACE - age,
            )
        return AccountAccess(mode="readonly", local_processing=False, remote_ai=False, export=True)


class StandaloneAccountService:
    """Local access used until the user's AuthProvider endpoint is configured."""

    def evaluate_access(
        self, now: datetime, provider_available: bool = False
    ) -> AccountAccess:
        return AccountAccess(
            mode="online",
            local_processing=True,
            remote_ai=False,
            export=True,
        )
