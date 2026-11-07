from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient

from blueframe.app import create_app
from blueframe.auth.service import AccountAccess
from blueframe.jobs.repository import JobRepository


class StaticAccountService:
    def __init__(self, mode: str = "online") -> None:
        self.access = AccountAccess(
            mode=mode,
            local_processing=mode != "readonly",
            remote_ai=mode == "online",
            export=True,
        )

    def evaluate_access(self, now, provider_available=False):
        return self.access


def test_protected_routes_require_current_session_token(
    migrated_session_factory,
) -> None:
    token = "a" * 64
    app = create_app(
        session_token=token,
        job_repository=JobRepository(
            migrated_session_factory, clock=lambda: datetime(2026, 11, 7, tzinfo=UTC)
        ),
        account_service=StaticAccountService(),
    )
    with TestClient(app) as client:
        assert client.get("/health").status_code == 200
        for headers in ({}, {"X-BlueFrame-Session": "malformed"}, {"X-BlueFrame-Session": "b" * 64}):
            response = client.get("/api/v1/system/status", headers=headers)
            assert response.status_code == 401
            assert token not in response.text
        valid = client.get(
            "/api/v1/system/status", headers={"X-BlueFrame-Session": token}
        )
        assert valid.status_code == 200
        assert valid.json()["status"] == "ok"


def test_account_route_exposes_exact_grace_seconds(migrated_session_factory) -> None:
    service = StaticAccountService("grace")
    service.access = service.access.model_copy(
        update={"grace_remaining": timedelta(hours=2, minutes=3, seconds=4)}
    )
    app = create_app(
        session_token="a" * 64,
        job_repository=JobRepository(migrated_session_factory),
        account_service=service,
    )
    with TestClient(app) as client:
        response = client.get(
            "/api/v1/account/access", headers={"X-BlueFrame-Session": "a" * 64}
        )
    assert response.json()["grace_remaining_seconds"] == 7384
