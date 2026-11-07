import importlib


class FakeWindowsCredentialApi:
    def __init__(self) -> None:
        self.values: dict[str, str] = {}

    def write(self, target: str, secret: str) -> None:
        self.values[target] = secret

    def read(self, target: str) -> str | None:
        return self.values.get(target)

    def delete(self, target: str) -> None:
        self.values.pop(target, None)


def test_memory_store_returns_reference_without_exposing_secret() -> None:
    module = importlib.import_module("blueframe.auth.credential_store")
    store = module.InMemoryCredentialStore()
    reference = store.put("account:user-1", "access-value")
    assert reference != "access-value"
    assert store.get(reference) == "access-value"
    store.delete(reference)
    assert store.get(reference) is None


def test_windows_store_round_trips_through_credential_api() -> None:
    module = importlib.import_module("blueframe.auth.credential_store")
    api = FakeWindowsCredentialApi()
    store = module.WindowsCredentialStore(api=api)

    reference = store.put("account:user-1", "access-value")

    assert reference == "wincred:BlueFrame/account:user-1"
    assert store.get(reference) == "access-value"
    store.delete(reference)
    assert store.get(reference) is None


def test_windows_store_rejects_non_blueframe_reference() -> None:
    module = importlib.import_module("blueframe.auth.credential_store")
    store = module.WindowsCredentialStore(api=FakeWindowsCredentialApi())

    try:
        store.get("memory:foreign")
    except ValueError as error:
        assert "invalid credential reference" in str(error)
    else:
        raise AssertionError("foreign reference must be rejected")
