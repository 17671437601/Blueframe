from datetime import UTC, datetime

from fastapi.testclient import TestClient

from blueframe.app import create_app
from blueframe.jobs.repository import JobRepository
from tests.api.test_security import StaticAccountService


TOKEN = "c" * 64
HEADERS = {"X-BlueFrame-Session": TOKEN}


def _client(session_factory, mode="online"):
    repository = JobRepository(
        session_factory, clock=lambda: datetime(2026, 11, 7, tzinfo=UTC)
    )
    app = create_app(
        session_token=TOKEN,
        job_repository=repository,
        account_service=StaticAccountService(mode),
    )
    return TestClient(app), repository


def test_job_routes_create_list_detail_and_map_control_errors(
    migrated_session_factory,
) -> None:
    client, repository = _client(migrated_session_factory)
    with client:
        created = client.post(
            "/api/v1/jobs",
            headers=HEADERS,
            json={"job_type": "render", "payload": {}, "idempotency_key": "api-1"},
        )
        assert created.status_code == 201
        job_id = created.json()["id"]
        assert client.get("/api/v1/jobs", headers=HEADERS).json()[0]["id"] == job_id
        assert client.get(f"/api/v1/jobs/{job_id}", headers=HEADERS).json()["status"] == "queued"
        assert client.get("/api/v1/jobs/missing", headers=HEADERS).status_code == 404
        assert client.post(f"/api/v1/jobs/{job_id}/resume", headers=HEADERS).status_code == 409
        assert client.post(f"/api/v1/jobs/{job_id}/cancel", headers=HEADERS).status_code == 200


def test_readonly_rejects_processing_but_allows_export(migrated_session_factory) -> None:
    client, _ = _client(migrated_session_factory, mode="readonly")
    with client:
        denied = client.post(
            "/api/v1/jobs", headers=HEADERS,
            json={"job_type": "render", "payload": {}, "idempotency_key": "denied"},
        )
        allowed = client.post(
            "/api/v1/jobs", headers=HEADERS,
            json={"job_type": "export_project", "payload": {}, "idempotency_key": "allowed"},
        )
        assert denied.status_code == 403
        assert allowed.status_code == 201
        assert client.get("/api/v1/jobs", headers=HEADERS).status_code == 200
