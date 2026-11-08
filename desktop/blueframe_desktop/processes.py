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

    def start(self, port: int, token: str, bridge_secret: str) -> str:
        context = multiprocessing.get_context("spawn")
        self.process = context.Process(
            target=_run_backend,
            args=(self.repository_root, self.data_dir, port, token, bridge_secret),
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


def _run_backend(
    repository_root: Path,
    data_dir: Path,
    port: int,
    token: str,
    bridge_secret: str,
) -> None:
    import os
    import sys

    backend_root = repository_root / "backend"
    sys.path.insert(0, str(backend_root))
    os.environ["BLUEFRAME_DATA_DIR"] = str(data_dir)

    import uvicorn
    from alembic import command
    from alembic.config import Config

    from blueframe.app import create_app
    from blueframe.auth.service import StandaloneAccountService
    from blueframe.auth.credential_store import WindowsCredentialStore
    from blueframe.asr.funasr_engine import FunAsrEngine
    from blueframe.asr.repository import AsrRepository
    from blueframe.asr.service import AsrService
    from blueframe.config import Settings
    from blueframe.db.engine import create_engine_and_session
    from blueframe.jobs.repository import JobRepository
    from blueframe.jobs.handlers.media import ProjectTranscriptionHandler
    from blueframe.jobs.handlers.analysis import ProjectAnalysisHandler
    from blueframe.media.preview import extract_audio
    from blueframe.media.probe import probe_media
    from blueframe.media.tools import discover_executables
    from blueframe.projects.repository import ProjectRepository
    from blueframe.providers.volcengine.config_service import ArkConfigService, DynamicArkAiProvider
    from blueframe.drama.analysis_service import AnalysisService
    from blueframe.drama.repository import StoryAnalysisRepository
    from blueframe.security.project_paths import ProjectPathRegistry
    from blueframe.workers.runner import WorkerRunner
    import threading

    alembic_config = Config(str(backend_root / "alembic.ini"))
    alembic_config.set_main_option("script_location", str(backend_root / "alembic"))
    command.upgrade(alembic_config, "head")

    settings = Settings(data_dir=data_dir, api_port=port)
    _engine, session_factory = create_engine_and_session(settings)
    jobs = JobRepository(session_factory)
    projects = ProjectRepository(session_factory)
    roots = ProjectPathRegistry()
    provider_config = ArkConfigService(
        data_dir / "providers.json", WindowsCredentialStore()
    )
    tools = discover_executables(search_roots=[repository_root.parent, repository_root])
    model_root = repository_root.parent / "model" / "hub" / "iic"
    asr_repository = AsrRepository(session_factory)
    analysis_repository = StoryAnalysisRepository(session_factory)
    asr = AsrService(
        asr_repository,
        FunAsrEngine(
            asr_model=model_root / "speech_seaco_paraformer_large_asr_nat-zh-cn-16k-common-vocab8404-pytorch",
            vad_model=model_root / "speech_fsmn_vad_zh-cn-16k-common-pytorch",
            punctuation_model=model_root / "punc_ct-transformer_zh-cn-common-vocab272727-pytorch",
        ),
        audio_extractor=lambda source, output: extract_audio(tools, source, output),
    )
    worker = WorkerRunner(
        jobs,
        {
            "transcribe_project": ProjectTranscriptionHandler(projects, asr),
            "analyze_project": ProjectAnalysisHandler(
                asr_repository,
                AnalysisService(DynamicArkAiProvider(provider_config), analysis_repository),
            ),
        },
        worker_id=f"desktop-{os.getpid()}",
        lease_seconds=settings.job_lease_seconds,
    )
    stop_worker = threading.Event()

    def worker_loop() -> None:
        while not stop_worker.is_set():
            if not worker.run_once():
                stop_worker.wait(0.25)

    threading.Thread(target=worker_loop, name="blueframe-worker", daemon=True).start()
    app = create_app(
        settings,
        session_token=token,
        job_repository=jobs,
        account_service=StandaloneAccountService(),
        project_repository=projects,
        project_path_registry=roots,
        media_probe=lambda path: probe_media(path, tools),
        bridge_secret=bridge_secret,
        provider_config_service=provider_config,
        analysis_repository=analysis_repository,
    )
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="warning")
