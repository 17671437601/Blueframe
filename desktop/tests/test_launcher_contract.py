from __future__ import annotations

from blueframe_desktop.launcher import launch


class FakeWindowRuntime:
    def __init__(self) -> None:
        self.window_options = None
        self.started = False

    def create_window(self, **options):
        self.window_options = options
        return object()

    def start(self) -> None:
        self.started = True


class FakeBackend:
    def __init__(self) -> None:
        self.started_with = None
        self.stopped = False

    def start(self, port: int, token: str) -> str:
        self.started_with = (port, token)
        return f"http://127.0.0.1:{port}"

    def stop(self) -> None:
        self.stopped = True


def test_launcher_contract_uses_in_memory_bridge_and_cleans_up(tmp_path) -> None:
    frontend = tmp_path / "index.html"
    frontend.write_text("<div id='app'></div>", encoding="utf-8")
    runtime = FakeWindowRuntime()
    backend = FakeBackend()

    result = launch(
        runtime=runtime,
        backend=backend,
        frontend_entry=frontend,
        token_factory=lambda: "d" * 64,
        port_factory=lambda: 43127,
        screen_size=(1920, 1080),
    )

    assert result == 0
    assert backend.stopped is True
    assert runtime.started is True
    options = runtime.window_options
    assert options["title"] == "蓝帧创作台"
    assert options["width"] >= 1366 and options["height"] >= 768
    assert options["min_size"] == (1024, 700)
    assert "d" * 64 not in options["url"]
    assert "token" not in options["url"].lower()
    assert options["js_api"].get_bootstrap() == {
        "apiBaseUrl": "http://127.0.0.1:43127",
        "sessionToken": "d" * 64,
    }
