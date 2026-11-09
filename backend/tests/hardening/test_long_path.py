from __future__ import annotations

from pathlib import Path

import pytest

from blueframe.security.project_paths import resolve_within_root


def test_long_relative_paths_stay_inside_the_root_without_truncation(tmp_path: Path) -> None:
    root = tmp_path / "项目根"
    root.mkdir()
    relative = "/".join(["深层目录" + "a" * 24] * 8) + "/最终成片.mp4"

    resolved = resolve_within_root(root, relative)

    assert len(str(root / relative)) > 260
    assert resolved.is_relative_to(root.resolve())
    assert resolved.name == "最终成片.mp4"


def test_long_path_traversal_is_still_rejected(tmp_path: Path) -> None:
    root = tmp_path / "root"
    root.mkdir()
    with pytest.raises(ValueError, match="escapes"):
        resolve_within_root(root, ("../" * 40) + "evil.mp4")


def test_deep_directories_work_when_windows_long_paths_are_enabled(tmp_path: Path) -> None:
    root = tmp_path / "deep"
    root.mkdir()
    target = root / ("/".join(["长目录" * 12] * 6))
    try:
        target.mkdir(parents=True)
    except OSError:
        pytest.skip("Windows long path support is not enabled")
    media = target / "成片.mp4"
    media.write_bytes(b"video")

    assert media.stat().st_size == 5
    assert resolve_within_root(root, media.relative_to(root).as_posix()).is_file()
