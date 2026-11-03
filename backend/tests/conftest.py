from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture
def unicode_data_dir(tmp_path: Path) -> Path:
    return tmp_path / "测试 项目"
