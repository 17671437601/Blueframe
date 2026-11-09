from blueframe.diagnostics.repository import DiagnosticsRepository


def test_diagnostics_repository_persists_only_structured_metrics(migrated_session_factory) -> None:
    repository = DiagnosticsRepository(migrated_session_factory)
    repository.record(category="provider", stage="analyze_story", status="completed", duration_ms=250, provider="volcengine", units=3)
    metric = repository.list()[0]
    assert metric["stage"] == "analyze_story"
    assert metric["duration_ms"] == 250
    assert set(metric) == {"category", "stage", "status", "duration_ms", "provider", "units", "error_code", "created_at"}
