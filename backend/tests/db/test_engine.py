from __future__ import annotations

import importlib
from pathlib import Path

from sqlalchemy import text


def test_file_database_enables_reliability_pragmas(unicode_data_dir: Path) -> None:
    config_module = importlib.import_module("blueframe.config")
    engine_module = importlib.import_module("blueframe.db.engine")
    database_path = unicode_data_dir / "blueframe.db"
    settings = config_module.Settings(
        data_dir=unicode_data_dir,
        database_url=f"sqlite:///{database_path.as_posix()}",
    )

    engine, session_factory = engine_module.create_engine_and_session(settings)

    with session_factory() as session:
        journal_mode = session.execute(text("PRAGMA journal_mode")).scalar_one()
        foreign_keys = session.execute(text("PRAGMA foreign_keys")).scalar_one()
        busy_timeout = session.execute(text("PRAGMA busy_timeout")).scalar_one()

    assert journal_mode == "wal"
    assert foreign_keys == 1
    assert busy_timeout >= 5_000
    assert database_path.is_file()

    engine.dispose()


def test_foreign_keys_are_enabled_on_each_connection(unicode_data_dir: Path) -> None:
    config_module = importlib.import_module("blueframe.config")
    engine_module = importlib.import_module("blueframe.db.engine")
    database_path = unicode_data_dir / "connections.db"
    settings = config_module.Settings(
        data_dir=unicode_data_dir,
        database_url=f"sqlite:///{database_path.as_posix()}",
    )
    engine, _ = engine_module.create_engine_and_session(settings)

    with engine.connect() as first, engine.connect() as second:
        assert first.execute(text("PRAGMA foreign_keys")).scalar_one() == 1
        assert second.execute(text("PRAGMA foreign_keys")).scalar_one() == 1

    engine.dispose()
