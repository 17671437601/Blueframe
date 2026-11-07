from __future__ import annotations

from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config

from blueframe.config import Settings
from blueframe.db.engine import create_engine_and_session


@pytest.fixture
def unicode_data_dir(tmp_path: Path) -> Path:
    return tmp_path / "测试 项目"


@pytest.fixture
def migrated_session_factory(tmp_path: Path, monkeypatch):
    data_dir = tmp_path / "数据库"
    monkeypatch.setenv("BLUEFRAME_DATA_DIR", str(data_dir))
    command.upgrade(Config(str(Path(__file__).parents[1] / "alembic.ini")), "head")
    engine, session_factory = create_engine_and_session(Settings(data_dir=data_dir))
    try:
        yield session_factory
    finally:
        engine.dispose()
