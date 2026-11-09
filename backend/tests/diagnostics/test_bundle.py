import json
import zipfile
from pathlib import Path

from blueframe.diagnostics.bundle import DiagnosticsBundleService
from blueframe.diagnostics.redact import redact
from blueframe.diagnostics.repository import DiagnosticsRepository
from blueframe.jobs.repository import JobRepository


def test_redaction_removes_secrets_paths_urls_and_personal_payloads(tmp_path: Path) -> None:
    private = {
        "token": "top-secret", "authorization": "Bearer hidden", "password": "pw",
        "nested": {"cookie": "sid=abc", "url": "https://example.test/a?key=secret&x=1"},
        "media_path": str(tmp_path / "私人视频.mp4"), "transcript": "用户字幕内容",
        "safe": "ok",
    }
    cleaned = redact(private)
    encoded = json.dumps(cleaned, ensure_ascii=False)
    assert "top-secret" not in encoded and "Bearer hidden" not in encoded and "sid=abc" not in encoded
    assert "私人视频" not in encoded and "用户字幕内容" not in encoded and "secret" not in encoded
    assert cleaned["safe"] == "ok"


def test_bundle_is_allowlisted_and_contains_no_job_payload_or_absolute_paths(migrated_session_factory, tmp_path: Path) -> None:
    jobs = JobRepository(migrated_session_factory)
    jobs.create("render_edit_plan", {"media_path": str(tmp_path / "private.mp4"), "transcript": "秘密字幕", "token": "secret"}, "job-1")
    metrics = DiagnosticsRepository(migrated_session_factory)
    metrics.record(category="worker", stage="render_media", status="completed", duration_ms=123, provider="ffmpeg", units=1)
    target = tmp_path / "diagnostics.zip"

    DiagnosticsBundleService(jobs, metrics).export(target, system={"app_version": "0.1.0", "data_dir": str(tmp_path)})

    with zipfile.ZipFile(target) as archive:
        assert set(archive.namelist()) == {"manifest.json", "system.json", "metrics.json", "jobs.json"}
        payload = b"".join(archive.read(name) for name in archive.namelist()).decode("utf-8")
    assert "secret" not in payload and "秘密字幕" not in payload and str(tmp_path) not in payload
    assert "render_media" in payload and "render_edit_plan" in payload
