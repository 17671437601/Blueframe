from __future__ import annotations

import importlib
from pathlib import Path

import pytest


def test_registered_unicode_root_round_trips_and_blocks_escape(tmp_path: Path) -> None:
    module = importlib.import_module("blueframe.security.project_paths")
    root = tmp_path / "测试 项目"
    root.mkdir()
    media = root / "第 1 集.mp4"
    media.write_bytes(b"video")
    registry = module.ProjectPathRegistry()
    root_id = registry.register(root)

    assert registry.resolve(root_id, "第 1 集.mp4") == media.resolve()
    for escaped in ("../outside.mp4", "..\\outside.mp4", str(tmp_path / "absolute.mp4")):
        with pytest.raises(ValueError):
            registry.resolve(root_id, escaped)
    with pytest.raises(KeyError):
        registry.resolve("missing", "file.mp4")


def test_registered_root_blocks_symlink_escape(tmp_path: Path) -> None:
    module = importlib.import_module("blueframe.security.project_paths")
    root = tmp_path / "project"
    outside = tmp_path / "outside"
    root.mkdir()
    outside.mkdir()
    link = root / "link"
    try:
        link.symlink_to(outside, target_is_directory=True)
    except OSError:
        pytest.skip("symlink creation is unavailable")
    registry = module.ProjectPathRegistry()
    root_id = registry.register(root)

    with pytest.raises(ValueError):
        registry.resolve(root_id, "link/escaped.mp4")
