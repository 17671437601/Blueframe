from __future__ import annotations

import secrets
import json
import os
import sys
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Protocol

from blueframe_desktop.processes import BackendSupervisor, find_free_port


class WindowRuntime(Protocol):
    def create_window(self, **options): ...
    def start(self) -> None: ...


class BackendRuntime(Protocol):
    def start(self, port: int, token: str, bridge_secret: str) -> str: ...
    def stop(self) -> None: ...


def _default_file_dialog() -> list[str]:
    import webview

    result = webview.windows[0].create_file_dialog(
        webview.OPEN_DIALOG,
        allow_multiple=True,
        file_types=("视频文件 (*.mp4;*.mov;*.mkv;*.avi;*.m4v)", "所有文件 (*.*)"),
    )
    return [] if result is None else [str(path) for path in result]


def _default_folder_dialog() -> str | None:
    import webview
    result = webview.windows[0].create_file_dialog(webview.FOLDER_DIALOG)
    if not result: return None
    return str(result[0] if isinstance(result, (list, tuple)) else result)


def _default_legacy_dialog() -> str | None:
    import webview
    result = webview.windows[0].create_file_dialog(
        webview.OPEN_DIALOG, allow_multiple=False,
        file_types=("旧版数据库 (video.db;*.db)", "SQLite 数据库 (*.db)", "所有文件 (*.*)"),
    )
    if not result: return None
    return str(result[0] if isinstance(result, (list, tuple)) else result)


def _register_root(api_base_url: str, bridge_secret: str, root: Path) -> str:
    body = json.dumps({"root_path": str(root)}).encode("utf-8")
    request = urllib.request.Request(
        f"{api_base_url}/internal/project-roots",
        data=body,
        headers={
            "Content-Type": "application/json",
            "X-BlueFrame-Bridge": bridge_secret,
        },
    )
    with urllib.request.urlopen(request, timeout=5) as response:
        return str(json.load(response)["root_id"])


def _open_project_output(api_base_url: str, bridge_secret: str, project_id: str) -> dict[str, bool]:
    request = urllib.request.Request(
        f"{api_base_url}/internal/projects/{project_id}/open-output",
        data=b"",
        headers={"X-BlueFrame-Bridge": bridge_secret},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=5) as response:
        return dict(json.load(response))


@dataclass(frozen=True)
class BootstrapBridge:
    api_base_url: str
    session_token: str
    bridge_secret: str
    file_dialog: Callable[[], list[str]] = _default_file_dialog
    folder_dialog: Callable[[], str | None] = _default_folder_dialog
    legacy_dialog: Callable[[], str | None] = _default_legacy_dialog
    root_registrar: Callable[[str, str, Path], str] = _register_root
    output_opener: Callable[[str, str, str], dict[str, bool]] = _open_project_output

    def get_bootstrap(self) -> dict[str, str]:
        return {
            "apiBaseUrl": self.api_base_url,
            "sessionToken": self.session_token,
        }

    def select_media_files(self) -> dict[str, object]:
        selected = [Path(path).resolve() for path in self.file_dialog()]
        if not selected:
            return {"rootId": None, "files": []}
        common = Path(os.path.commonpath([str(path) for path in selected]))
        root = common.parent if len(selected) == 1 or common.is_file() else common
        root_id = self.root_registrar(self.api_base_url, self.bridge_secret, root)
        return {
            "rootId": root_id,
            "files": [path.relative_to(root).as_posix() for path in selected],
        }

    def select_project_directory(self) -> dict[str, str | None]:
        selected = self.folder_dialog()
        if not selected: return {"rootId": None}
        root = Path(selected).resolve()
        root_id = self.root_registrar(self.api_base_url, self.bridge_secret, root)
        return {"rootId": root_id}

    def select_legacy_database(self) -> dict[str, str | None]:
        selected = self.legacy_dialog()
        if not selected: return {"rootId": None, "file": None}
        database = Path(selected).resolve()
        root_id = self.root_registrar(self.api_base_url, self.bridge_secret, database.parent)
        return {"rootId": root_id, "file": database.name}

    def open_project_output(self, project_id: str) -> dict[str, bool]:
        return self.output_opener(self.api_base_url, self.bridge_secret, project_id)


def launch(
    *,
    runtime: WindowRuntime,
    backend: BackendRuntime,
    frontend_entry: Path,
    token_factory: Callable[[], str] = lambda: secrets.token_hex(32),
    bridge_secret_factory: Callable[[], str] = lambda: secrets.token_hex(32),
    port_factory: Callable[[], int] = find_free_port,
    screen_size: tuple[int, int] | None = None,
) -> int:
    if not frontend_entry.is_file():
        raise RuntimeError("Frontend build is missing; run npm run build first")
    token = token_factory()
    bridge_secret = bridge_secret_factory()
    port = port_factory()
    width = 1366 if screen_size is None else min(1366, screen_size[0])
    height = 768 if screen_size is None else min(768, screen_size[1])
    try:
        api_base_url = backend.start(port, token, bridge_secret)
        runtime.create_window(
            title="蓝帧创作台",
            url=frontend_entry.resolve().as_uri(),
            js_api=BootstrapBridge(api_base_url, token, bridge_secret),
            width=width,
            height=height,
            min_size=(1024, 700),
            background_color="#f2f6fc",
        )
        runtime.start()
        return 0
    finally:
        backend.stop()


def _data_directory(repository_root: Path) -> Path:
    # Packaged installs are uninstalled by deleting the install tree, so user
    # databases must live outside it.
    if getattr(sys, "frozen", False):
        local_app_data = os.environ.get("LOCALAPPDATA")
        if local_app_data:
            return Path(local_app_data) / "BlueFrameStudio" / "data"
    return repository_root / ".blueframe-data"


def main() -> int:
    if "--smoke" in sys.argv:
        from blueframe_desktop.package_smoke import main as smoke_main
        return smoke_main()
    import webview

    repository_root = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[2])).resolve()
    return launch(
        runtime=webview,
        backend=BackendSupervisor(repository_root, _data_directory(repository_root)),
        frontend_entry=repository_root / "frontend" / "dist" / "index.html",
    )


if __name__ == "__main__":
    raise SystemExit(main())
