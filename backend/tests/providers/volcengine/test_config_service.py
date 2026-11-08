from pathlib import Path

from fastapi.testclient import TestClient

from blueframe.app import create_app
from blueframe.auth.credential_store import InMemoryCredentialStore
from blueframe.providers.volcengine.config_service import ArkConfigService
from blueframe.providers.volcengine.tts import VolcengineTtsConfigService


HEADERS = {"X-BlueFrame-Session": "a" * 64}


def test_config_service_persists_reference_not_secret(tmp_path: Path) -> None:
    credentials = InMemoryCredentialStore()
    service = ArkConfigService(tmp_path / "providers.json", credentials)

    status = service.configure(model="ep-test", api_key="secret-value")

    assert status.configured is True
    assert status.model == "ep-test"
    assert "secret-value" not in (tmp_path / "providers.json").read_text("utf-8")
    assert "credential_reference" in (tmp_path / "providers.json").read_text("utf-8")


def test_replacing_a_fixed_windows_reference_keeps_the_new_secret(tmp_path: Path) -> None:
    class FixedCredentials:
        value: str | None = None

        def put(self, _name: str, secret: str) -> str:
            self.value = secret
            return "wincred:BlueFrame/provider:volcengine-ark"

        def get(self, _reference: str) -> str | None:
            return self.value

        def delete(self, _reference: str) -> None:
            self.value = None

    credentials = FixedCredentials()
    service = ArkConfigService(tmp_path / "providers.json", credentials)
    service.configure(model="ep-one", api_key="old")
    service.configure(model="ep-two", api_key="new")

    assert credentials.value == "new"
    assert service.status().configured is True


def test_provider_settings_api_never_returns_api_key(tmp_path: Path) -> None:
    service = ArkConfigService(tmp_path / "providers.json", InMemoryCredentialStore())
    app = create_app(
        session_token="a" * 64,
        provider_config_service=service,
    )
    with TestClient(app) as client:
        initial = client.get("/api/v1/providers/volcengine", headers=HEADERS)
        saved = client.put(
            "/api/v1/providers/volcengine",
            headers=HEADERS,
            json={"model": "ep-test", "api_key": "secret-value"},
        )
        fetched = client.get("/api/v1/providers/volcengine", headers=HEADERS)

    assert initial.json() == {"configured": False, "model": None}
    assert saved.status_code == 200
    assert fetched.json() == {"configured": True, "model": "ep-test"}
    assert "secret-value" not in saved.text + fetched.text


def test_tts_settings_api_persists_only_credential_reference(tmp_path: Path) -> None:
    credentials = InMemoryCredentialStore()
    service = VolcengineTtsConfigService(tmp_path / "tts-provider.json", credentials)
    app = create_app(session_token="a" * 64, tts_config_service=service)

    with TestClient(app) as client:
        saved = client.put(
            "/api/v1/providers/volcengine-tts",
            headers=HEADERS,
            json={"default_voice": "zh_female_vv_uranus_bigtts", "api_key": "tts-secret"},
        )
        fetched = client.get("/api/v1/providers/volcengine-tts", headers=HEADERS)

    persisted = (tmp_path / "tts-provider.json").read_text("utf-8")
    assert saved.json() == {"configured": True, "default_voice": "zh_female_vv_uranus_bigtts"}
    assert fetched.json() == saved.json()
    assert "tts-secret" not in saved.text + fetched.text + persisted
    assert "credential_reference" in persisted
