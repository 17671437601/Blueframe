from __future__ import annotations

import secrets
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Protocol

from blueframe_desktop.processes import BackendSupervisor, find_free_port


class WindowRuntime(Protocol):
    def create_window(self, **options): ...
    def start(self) -> None: ...


class BackendRuntime(Protocol):
    def start(self, port: int, token: str) -> str: ...
    def stop(self) -> None: ...


@dataclass(frozen=True)
class BootstrapBridge:
    api_base_url: str
    session_token: str

    def get_bootstrap(self) -> dict[str, str]:
        return {
            "apiBaseUrl": self.api_base_url,
            "sessionToken": self.session_token,
        }


def launch(
    *,
    runtime: WindowRuntime,
    backend: BackendRuntime,
    frontend_entry: Path,
    token_factory: Callable[[], str] = lambda: secrets.token_hex(32),
    port_factory: Callable[[], int] = find_free_port,
    screen_size: tuple[int, int] | None = None,
) -> int:
    if not frontend_entry.is_file():
        raise RuntimeError("Frontend build is missing; run npm run build first")
    token = token_factory()
    port = port_factory()
    width = 1366 if screen_size is None else min(1366, screen_size[0])
    height = 768 if screen_size is None else min(768, screen_size[1])
    try:
        api_base_url = backend.start(port, token)
        runtime.create_window(
            title="蓝帧创作台",
            url=frontend_entry.resolve().as_uri(),
            js_api=BootstrapBridge(api_base_url, token),
            width=width,
            height=height,
            min_size=(1024, 700),
            background_color="#f2f6fc",
        )
        runtime.start()
        return 0
    finally:
        backend.stop()


def main() -> int:
    import webview

    repository_root = Path(__file__).resolve().parents[2]
    return launch(
        runtime=webview,
        backend=BackendSupervisor(repository_root),
        frontend_entry=repository_root / "frontend" / "dist" / "index.html",
    )


if __name__ == "__main__":
    raise SystemExit(main())
