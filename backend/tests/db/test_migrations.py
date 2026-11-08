from __future__ import annotations

import sqlite3
from pathlib import Path

from alembic import command
from alembic.config import Config


def test_upgrade_head_is_repeatable_and_records_revision(
    tmp_path: Path, monkeypatch
) -> None:
    data_dir = tmp_path / "迁移 数据"
    monkeypatch.setenv("BLUEFRAME_DATA_DIR", str(data_dir))
    config = Config(str(Path(__file__).resolve().parents[2] / "alembic.ini"))

    command.upgrade(config, "head")
    command.upgrade(config, "head")

    connection = sqlite3.connect(data_dir / "blueframe.db")
    try:
        revisions = connection.execute(
            "SELECT version_num FROM alembic_version"
        ).fetchall()
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
    finally:
        connection.close()

    assert revisions == [("0009_live_recordings",)]
    assert {
        "account_summary",
        "entitlement_snapshot",
        "projects",
        "project_sources",
        "asr_documents",
        "asr_lines",
        "story_analysis_versions",
        "edit_plans",
        "render_artifacts",
        "commentary_script_versions",
        "assets",
        "variant_batches",
        "variant_items",
        "recording_sessions",
        "recording_segments",
    } <= tables
