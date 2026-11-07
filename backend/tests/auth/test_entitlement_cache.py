from __future__ import annotations

import json
import importlib
from datetime import UTC, datetime, timedelta
from pathlib import Path

from alembic import command
from alembic.config import Config

from blueframe.auth.entitlement_cache import EntitlementSnapshot
from blueframe.config import Settings
from blueframe.db.engine import create_engine_and_session
from blueframe.providers.auth import Entitlements, UserProfile


def test_sqlite_cache_persists_verified_snapshot_without_token_values(
    tmp_path: Path, monkeypatch
) -> None:
    now = datetime(2026, 11, 3, tzinfo=UTC)
    data_dir = tmp_path / "账号 数据"
    monkeypatch.setenv("BLUEFRAME_DATA_DIR", str(data_dir))
    command.upgrade(
        Config(str(Path(__file__).resolve().parents[2] / "alembic.ini")), "head"
    )
    settings = Settings(data_dir=data_dir)
    engine, session_factory = create_engine_and_session(settings)
    entitlements = Entitlements(
        user_id="user-1",
        features={"local_asr", "remote_ai"},
        valid_from=now - timedelta(days=1),
        valid_until=now + timedelta(days=30),
        concurrency_limit=2,
        daily_units=100,
        monthly_units=1000,
        ai_tiers={"pro"},
        tts_tiers={"standard"},
    )
    payload = json.dumps(entitlements.model_dump(mode="json"), ensure_ascii=False)
    cache_type = getattr(
        importlib.import_module("blueframe.auth.entitlement_cache"),
        "SqliteEntitlementCache",
    )
    cache = cache_type(
        session_factory, signature_verifier=lambda raw, signature: signature == "valid"
    )
    snapshot = EntitlementSnapshot(
        entitlements=entitlements,
        verified_at=now,
        token_expires_at=now + timedelta(hours=1),
        signature_valid=True,
        subject_user_id="user-1",
    )

    cache.save(
        profile=UserProfile(user_id="user-1", display_name="测试用户"),
        credential_reference="wincred:BlueFrame/account:user-1",
        snapshot=snapshot,
        signed_payload=payload,
        signature="valid",
    )
    cache.update_last_evaluated(now + timedelta(hours=3))
    restored = cache.get_snapshot()

    assert restored == snapshot
    assert cache.last_evaluated_at == now + timedelta(hours=3)
    database_bytes = (data_dir / "blueframe.db").read_bytes()
    assert b"access-value" not in database_bytes
    assert b"refresh-value" not in database_bytes
    engine.dispose()


def test_sqlite_cache_marks_bad_signature_untrusted(tmp_path: Path, monkeypatch) -> None:
    now = datetime(2026, 11, 3, tzinfo=UTC)
    data_dir = tmp_path / "bad-signature"
    monkeypatch.setenv("BLUEFRAME_DATA_DIR", str(data_dir))
    command.upgrade(
        Config(str(Path(__file__).resolve().parents[2] / "alembic.ini")), "head"
    )
    engine, session_factory = create_engine_and_session(Settings(data_dir=data_dir))
    cache_type = getattr(
        importlib.import_module("blueframe.auth.entitlement_cache"),
        "SqliteEntitlementCache",
    )
    cache = cache_type(session_factory, signature_verifier=lambda *_: False)
    entitlements = Entitlements(
        user_id="user-1",
        features={"local_asr"},
        valid_from=now - timedelta(days=1),
        valid_until=now + timedelta(days=1),
        concurrency_limit=1,
        daily_units=1,
        monthly_units=1,
        ai_tiers=set(),
        tts_tiers=set(),
    )
    cache.save(
        profile=UserProfile(user_id="user-1", display_name="User"),
        credential_reference="wincred:BlueFrame/account:user-1",
        snapshot=EntitlementSnapshot(
            entitlements=entitlements,
            verified_at=now,
            token_expires_at=now + timedelta(hours=1),
            signature_valid=True,
            subject_user_id="user-1",
        ),
        signed_payload=json.dumps(entitlements.model_dump(mode="json")),
        signature="tampered",
    )

    assert cache.get_snapshot() is None
    engine.dispose()
