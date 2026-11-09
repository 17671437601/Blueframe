import zipfile
from pathlib import Path

from fastapi.testclient import TestClient

from blueframe.app import create_app
from blueframe.auth.service import StandaloneAccountService
from blueframe.diagnostics.bundle import DiagnosticsBundleService
from blueframe.diagnostics.repository import DiagnosticsRepository
from blueframe.jobs.repository import JobRepository


def test_diagnostics_api_exports_allowlisted_bundle(migrated_session_factory, tmp_path: Path) -> None:
    jobs = JobRepository(migrated_session_factory); metrics = DiagnosticsRepository(migrated_session_factory)
    jobs.create("render", {"token": "private"}, "one")
    app = create_app(
        session_token="a" * 64, job_repository=jobs, account_service=StandaloneAccountService(),
        diagnostics_service=DiagnosticsBundleService(jobs, metrics), diagnostics_export_dir=tmp_path / "exports",
    )
    headers = {"X-BlueFrame-Session": "a" * 64}
    with TestClient(app) as client:
        summary = client.get("/api/v1/diagnostics/summary", headers=headers)
        exported = client.post("/api/v1/diagnostics/export", headers=headers)
    target = tmp_path / "exports" / exported.json()["filename"]
    assert summary.status_code == 200 and summary.json()["job_count"] == 1
    assert exported.status_code == 201 and target.is_file()
    with zipfile.ZipFile(target) as archive:
        assert "private" not in b"".join(archive.read(name) for name in archive.namelist()).decode()
