from __future__ import annotations

import multiprocessing
import socket
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Callable, Protocol


class ManagedProcess(Protocol):
    def is_alive(self) -> bool: ...
    def terminate(self) -> None: ...
    def join(self, timeout: float) -> None: ...
    def kill(self) -> None: ...


def find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.bind(("127.0.0.1", 0))
        return int(listener.getsockname()[1])


def _probe(url: str) -> bool:
    try:
        with urllib.request.urlopen(url, timeout=0.5) as response:
            return response.status == 200
    except (OSError, urllib.error.URLError):
        return False


def wait_for_health(
    url: str,
    *,
    timeout: float = 15,
    probe: Callable[[str], bool] = _probe,
    sleep: Callable[[float], None] = time.sleep,
) -> bool:
    deadline = time.monotonic() + timeout
    while True:
        if probe(url):
            return True
        if time.monotonic() >= deadline:
            raise RuntimeError("BlueFrame local service did not become healthy in time")
        sleep(0.1)


def stop_process(process: ManagedProcess | None, *, timeout: float = 5) -> None:
    if process is None or not process.is_alive():
        return
    process.terminate()
    process.join(timeout)
    if process.is_alive():
        process.kill()
        process.join(timeout)


class BackendSupervisor:
    def __init__(self, repository_root: Path, data_dir: Path | None = None) -> None:
        self.repository_root = repository_root.resolve()
        self.data_dir = (data_dir or (self.repository_root / ".blueframe-data")).resolve()
        self.process: ManagedProcess | None = None

    def start(self, port: int, token: str) -> str:
        context = multiprocessing.get_context("spawn")
        self.process = context.Process(
            target=_run_backend,
            args=(self.repository_root, self.data_dir, port, token),
            name="blueframe-local-api",
        )
        self.process.start()
        base_url = f"http://127.0.0.1:{port}"
        try:
            wait_for_health(f"{base_url}/health")
        except BaseException:
            self.stop()
            raise
        return base_url

    def stop(self) -> None:
        stop_process(self.process)
        self.process = None


def _run_backend(repository_root: Path, data_dir: Path, port: int, token: str) -> None:
    import os
    import sys

    backend_root = repository_root / "backend"
    sys.path.insert(0, str(backend_root))
    os.environ["BLUEFRAME_DATA_DIR"] = str(data_dir)

    import uvicorn
    from alembic import command
    from alembic.config import Config

    from blueframe.app import create_app
    from blueframe.auth.entitlement_cache import InMemoryEntitlementCache
    from blueframe.auth.service import AccountService
    from blueframe.config import Settings
    from blueframe.db.engine import create_engine_and_session
    from blueframe.jobs.repository import JobRepository

    alembic_config = Config(str(backend_root / "alembic.ini"))
    alembic_config.set_main_option("script_location", str(backend_root / "alembic"))
    command.upgrade(alembic_config, "head")

    settings = Settings(data_dir=data_dir, api_port=port)
    _engine, session_factory = create_engine_and_session(settings)
    app = create_app(
        settings,
        session_token=token,
        job_repository=JobRepository(session_factory),
        account_service=AccountService(InMemoryEntitlementCache()),
    )
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="warning")
