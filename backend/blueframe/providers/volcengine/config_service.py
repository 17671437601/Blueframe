from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from blueframe.auth.credential_store import CredentialStore
from blueframe.providers.volcengine.config import ArkProviderConfig


class ArkConfigStatus(BaseModel):
    model_config = ConfigDict(frozen=True)

    configured: bool
    model: str | None


class ArkConfigService:
    def __init__(self, path: Path, credential_store: CredentialStore) -> None:
        self.path = path
        self.credential_store = credential_store

    def status(self) -> ArkConfigStatus:
        config = self.load()
        return ArkConfigStatus(
            configured=config is not None
            and self.credential_store.get(config.credential_reference) is not None,
            model=config.model if config else None,
        )

    def load(self) -> ArkProviderConfig | None:
        if not self.path.exists():
            return None
        return ArkProviderConfig.model_validate_json(self.path.read_text("utf-8"))

    def configure(self, *, model: str, api_key: str | None = None) -> ArkConfigStatus:
        current = self.load()
        if api_key:
            reference = self.credential_store.put("provider:volcengine-ark", api_key)
            if current is not None and current.credential_reference != reference:
                self.credential_store.delete(current.credential_reference)
        elif current is not None:
            reference = current.credential_reference
        else:
            raise ValueError("API key is required for initial configuration")
        config = ArkProviderConfig(credential_reference=reference, model=model)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(".tmp")
        temporary.write_text(config.model_dump_json(indent=2), encoding="utf-8")
        temporary.replace(self.path)
        return self.status()
