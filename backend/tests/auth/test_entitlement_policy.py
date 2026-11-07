from datetime import UTC, datetime, timedelta
import importlib


def _build_service(now, *, token_expires=None, valid=True):
    auth = importlib.import_module("blueframe.providers.auth")
    cache = importlib.import_module("blueframe.auth.entitlement_cache")
    service = importlib.import_module("blueframe.auth.service")
    entitlements = auth.Entitlements(
        user_id="user-1", features={"local_asr", "remote_ai"},
        valid_from=now - timedelta(days=1), valid_until=now + timedelta(days=30),
        concurrency_limit=2, daily_units=100, monthly_units=1000,
        ai_tiers={"pro"}, tts_tiers={"standard"},
    )
    snapshot = cache.EntitlementSnapshot(
        entitlements=entitlements, verified_at=now,
        token_expires_at=token_expires or now + timedelta(hours=1),
        signature_valid=valid, subject_user_id="user-1",
    )
    return service.AccountService(cache.InMemoryEntitlementCache(snapshot))


def test_outage_policy_has_exact_72_hour_boundary() -> None:
    started = datetime(2026, 11, 3, tzinfo=UTC)
    service = _build_service(started, token_expires=started + timedelta(hours=2))

    online = service.evaluate_access(started, provider_available=True)
    grace = service.evaluate_access(started + timedelta(hours=71, minutes=59, seconds=59))
    expired = service.evaluate_access(started + timedelta(hours=72))

    assert (online.mode, online.local_processing, online.remote_ai, online.export) == ("online", True, True, True)
    assert (grace.mode, grace.local_processing, grace.remote_ai) == ("grace", True, False)
    assert grace.grace_remaining == timedelta(seconds=1)
    assert (expired.mode, expired.local_processing, expired.remote_ai, expired.export) == ("readonly", False, False, True)


def test_clock_rollback_cannot_increase_remaining_grace() -> None:
    started = datetime(2026, 11, 3, tzinfo=UTC)
    service = _build_service(started)
    later = service.evaluate_access(started + timedelta(hours=60))
    rolled_back = service.evaluate_access(started + timedelta(hours=2))
    assert rolled_back.grace_remaining == later.grace_remaining == timedelta(hours=12)


def test_invalid_or_mismatched_snapshot_is_readonly() -> None:
    now = datetime(2026, 11, 3, tzinfo=UTC)
    invalid = _build_service(now, valid=False).evaluate_access(now)
    assert invalid.mode == "readonly"
    assert invalid.export is True
