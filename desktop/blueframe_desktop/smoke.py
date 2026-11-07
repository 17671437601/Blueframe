from __future__ import annotations

import json
import secrets
import tempfile
import urllib.error
import urllib.request
from datetime import UTC, datetime, timedelta
from pathlib import Path

from blueframe.config import Settings
from blueframe.db.engine import create_engine_and_session
from blueframe.jobs.repository import JobRepository
from blueframe.workers.recovery import recover_expired_leases
from blueframe_desktop.processes import BackendSupervisor, find_free_port


def _request(url: str, token: str | None = None, payload: dict | None = None):
    headers = {"Accept": "application/json"}
    if token:
        headers["X-BlueFrame-Session"] = token
    data = None
    if payload is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(url, headers=headers, data=data)
    with urllib.request.urlopen(request, timeout=3) as response:
        return response.status, json.load(response)


def main() -> int:
    repository_root = Path(__file__).resolve().parents[2]
    with tempfile.TemporaryDirectory(prefix="blueframe-smoke-") as temporary:
        data_dir = Path(temporary).resolve()
        if not data_dir.name.startswith("blueframe-smoke-"):
            raise RuntimeError("Refusing to use an unvalidated smoke directory")
        token = secrets.token_hex(32)
        port = find_free_port()
        supervisor = BackendSupervisor(repository_root, data_dir)
        base_url = supervisor.start(port, token)
        try:
            status, health = _request(f"{base_url}/health")
            assert status == 200 and health["database"] == "ok"
            try:
                _request(f"{base_url}/api/v1/system/status")
                raise AssertionError("protected API accepted an unauthenticated request")
            except urllib.error.HTTPError as error:
                assert error.code == 401
            _, account = _request(f"{base_url}/api/v1/account/access", token)
            assert account["mode"] == "readonly"
            status, job = _request(
                f"{base_url}/api/v1/jobs",
                token,
                {"job_type": "export_project", "payload": {}, "idempotency_key": "smoke-export"},
            )
            assert status == 201 and job["status"] == "queued"
        finally:
            supervisor.stop()

        now = datetime.now(UTC)
        engine, session_factory = create_engine_and_session(Settings(data_dir=data_dir))
        repository = JobRepository(session_factory, clock=lambda: now)
        claimed = repository.claim_next("smoke-worker", lease_seconds=1)
        assert claimed is not None
        assert recover_expired_leases(
            repository, now=now + timedelta(seconds=2), max_attempts=3
        ) == 1
        assert repository.get(claimed.id).status == "queued"
        engine.dispose()
    print("BlueFrame smoke checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
