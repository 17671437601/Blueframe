from __future__ import annotations

from datetime import datetime
from typing import Any, Protocol, runtime_checkable

from pydantic import Field, model_validator, field_validator

from blueframe.domain.common import DomainModel, require_aware


class AuthSession(DomainModel):
    access_token: str = Field(min_length=1)
    refresh_token: str = Field(min_length=1)
    expires_at: datetime

    _aware = field_validator("expires_at")(require_aware)


class UserProfile(DomainModel):
    user_id: str = Field(min_length=1)
    display_name: str = Field(min_length=1)


class Entitlements(DomainModel):
    user_id: str = Field(min_length=1)
    features: set[str]
    valid_from: datetime
    valid_until: datetime
    concurrency_limit: int = Field(ge=0)
    daily_units: int = Field(ge=0)
    monthly_units: int = Field(ge=0)
    ai_tiers: set[str]
    tts_tiers: set[str]

    _aware_dates = field_validator("valid_from", "valid_until")(require_aware)

    @model_validator(mode="after")
    def valid_date_order(self) -> "Entitlements":
        if self.valid_until <= self.valid_from:
            raise ValueError("valid_until must be after valid_from")
        return self


class UsageEvent(DomainModel):
    feature: str = Field(min_length=1)
    units: int = Field(gt=0)
    occurred_at: datetime

    _aware = field_validator("occurred_at")(require_aware)


class Ack(DomainModel):
    accepted: bool


@runtime_checkable
class AuthProvider(Protocol):
    async def login(self, credentials: dict[str, Any]) -> AuthSession: ...
    async def refresh(self, refresh_token: str) -> AuthSession: ...
    async def current_user(self, access_token: str) -> UserProfile: ...
    async def get_entitlements(self, access_token: str) -> Entitlements: ...
    async def report_usage(self, access_token: str, usage_event: UsageEvent) -> Ack: ...
    async def logout(self, access_token: str) -> None: ...
