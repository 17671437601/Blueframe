from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ArkProviderConfig(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    credential_reference: str = Field(min_length=1, repr=False)
    model: str = Field(min_length=1)
    base_url: Literal["https://ark.cn-beijing.volces.com/api/v3"] = (
        "https://ark.cn-beijing.volces.com/api/v3"
    )
    timeout_seconds: float = Field(default=60, ge=1, le=300)
    max_attempts: int = Field(default=3, ge=1, le=5)
    max_output_tokens: int = Field(default=8192, ge=128, le=262144)

    @property
    def responses_url(self) -> str:
        return f"{self.base_url}/responses"
