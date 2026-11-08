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

    def start(self, port: int, token: str, bridge_secret: str) -> str:
        self.started_with = (port, token, bridge_secret)
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
        bridge_secret_factory=lambda: "bridge-only-secret",
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
    assert "bridge-only-secret" not in options["js_api"].get_bootstrap().values()


def test_bridge_file_selection_returns_only_root_id_and_relative_paths(tmp_path) -> None:
    from blueframe_desktop.launcher import BootstrapBridge

    root = tmp_path / "中文 剧集"
    root.mkdir()
    first = root / "01.mp4"
    second = root / "02.mp4"
    first.touch(); second.touch()
    bridge = BootstrapBridge(
        "http://127.0.0.1:43127",
        "d" * 64,
        "bridge-secret",
        file_dialog=lambda: [str(first), str(second)],
        root_registrar=lambda _url, _secret, selected_root: "root-id" if selected_root == root else "wrong",
    )

    selection = bridge.select_media_files()

    assert selection == {"rootId": "root-id", "files": ["01.mp4", "02.mp4"]}
    assert str(root) not in str(selection)


def test_bridge_opens_output_without_exposing_bridge_secret() -> None:
    from blueframe_desktop.launcher import BootstrapBridge

    calls = []
    bridge = BootstrapBridge(
        "http://127.0.0.1:43127", "d" * 64, "bridge-secret",
        output_opener=lambda url, secret, project: calls.append((url, secret, project)) or {"opened": True},
    )
    assert bridge.open_project_output("project-1") == {"opened": True}
    assert calls == [("http://127.0.0.1:43127", "bridge-secret", "project-1")]


def test_bridge_directory_selection_returns_only_registered_root_id(tmp_path) -> None:
    from blueframe_desktop.launcher import BootstrapBridge
    bridge = BootstrapBridge(
        "http://127.0.0.1:43127", "d" * 64, "bridge-secret",
        folder_dialog=lambda: str(tmp_path),
        root_registrar=lambda _url, _secret, root: "live-root" if root == tmp_path.resolve() else "wrong",
    )
    assert bridge.select_project_directory() == {"rootId": "live-root"}
