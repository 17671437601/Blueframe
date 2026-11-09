from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path


def main() -> int:
    from alembic import command
    from alembic.config import Config
    from blueframe_desktop.resources import discover_runtime_resources

    root = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[2]))
    resources = discover_runtime_resources(base_dir=root) if (root / "resource-manifest.json").is_file() else discover_runtime_resources(repository_root=root)
    frontend = root / "frontend" / "dist" / "index.html"
    if not frontend.is_file(): raise RuntimeError("offline frontend is missing")
    for module in ("fastapi", "funasr", "torch", "webview"):
        __import__(module)
    import torch
    converted = torch.tensor([1.0]).numpy()
    if converted.tolist() != [1.0]: raise RuntimeError("Torch/NumPy offline runtime is incompatible")
    version = subprocess.run([str(resources.ffprobe), "-version"], capture_output=True, timeout=10, shell=False)
    if version.returncode != 0: raise RuntimeError("bundled FFprobe failed")
    with tempfile.TemporaryDirectory(prefix="blueframe-package-smoke-") as temporary:
        config = Config(str(root / "backend" / "alembic.ini"))
        config.set_main_option("script_location", str(root / "backend" / "alembic"))
        config.set_main_option("sqlalchemy.url", f"sqlite:///{(Path(temporary) / 'smoke.db').as_posix()}")
        command.upgrade(config, "head")
    print("BlueFrame packaged smoke checks passed")
    return 0
