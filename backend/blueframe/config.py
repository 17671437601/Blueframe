from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="BLUEFRAME_",
        env_file=".env",
        extra="ignore",
    )

    data_dir: Path = Path.cwd() / ".blueframe-data"
    database_url: str = ""
    api_host: Literal["127.0.0.1"] = "127.0.0.1"
    api_port: int = 0
    job_lease_seconds: int = 60
    entitlement_grace_hours: Literal[72] = 72

    @model_validator(mode="after")
    def populate_database_url(self) -> "Settings":
        self.data_dir = self.data_dir.expanduser().resolve()
        if not self.database_url:
            database_path = (self.data_dir / "blueframe.db").as_posix()
            self.database_url = f"sqlite:///{database_path}"
        return self
