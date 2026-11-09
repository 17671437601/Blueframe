from __future__ import annotations

import json
import os
import platform
import zipfile
from datetime import UTC, datetime
from pathlib import Path

from blueframe.diagnostics.redact import redact


class DiagnosticsBundleService:
    def __init__(self, jobs, metrics) -> None:
        self.jobs, self.metrics = jobs, metrics

    def summary(self) -> dict:
        jobs = self.jobs.list()
        return {
            "job_count": len(jobs), "failed_jobs": sum(job.status.value == "failed" for job in jobs),
            "metric_count": len(self.metrics.list()),
        }

    def export(self, target: Path, *, system: dict | None = None) -> Path:
        target = target.resolve(); target.parent.mkdir(parents=True, exist_ok=True)
        allowed_system = {"app_version", "platform", "python_version", "architecture"}
        system_payload = {
            "platform": platform.system(), "python_version": platform.python_version(),
            "architecture": platform.machine(),
            **{key: value for key, value in (system or {}).items() if key in allowed_system},
        }
        jobs_payload = [{
            "job_type": job.job_type, "status": job.status.value, "progress": job.progress,
            "stage": job.stage, "attempts": job.attempts, "error_code": job.error_code,
            "created_at": job.created_at.isoformat(), "updated_at": job.updated_at.isoformat(),
        } for job in self.jobs.list()]
        files = {
            "system.json": redact(system_payload), "metrics.json": redact(self.metrics.list()),
            "jobs.json": redact(jobs_payload),
            "manifest.json": {"format": "blueframe-diagnostics-v1", "created_at": datetime.now(UTC).isoformat(),
                              "files": ["system.json", "metrics.json", "jobs.json"]},
        }
        temporary = target.with_suffix(target.suffix + ".tmp")
        try:
            with zipfile.ZipFile(temporary, "w", compression=zipfile.ZIP_DEFLATED) as archive:
                for name, payload in files.items():
                    archive.writestr(name, json.dumps(payload, ensure_ascii=False, indent=2))
            os.replace(temporary, target)
        finally:
            temporary.unlink(missing_ok=True)
        return target
