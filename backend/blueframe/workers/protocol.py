from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from blueframe.jobs.models import Job


@dataclass(frozen=True)
class JobResult:
    artifacts: tuple[str, ...] = ()


class WorkerControl(Protocol):
    def heartbeat(self) -> None: ...
    def checkpoint(self, data: dict[str, Any]) -> None: ...
    def progress(self, value: float, stage: str | None = None) -> None: ...
    @property
    def pause_requested(self) -> bool: ...
    @property
    def cancel_requested(self) -> bool: ...


class JobHandler(Protocol):
    def run(
        self, job: Job, checkpoint: dict[str, Any] | None, control: WorkerControl
    ) -> JobResult: ...
