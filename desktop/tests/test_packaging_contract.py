from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_windows_package_contract_includes_offline_ui_tools_models_and_smoke() -> None:
    spec = (ROOT / "packaging" / "blueframe-studio.spec").read_text(encoding="utf-8")
    build = (ROOT / "scripts" / "build-windows.ps1").read_text(encoding="utf-8")
    verify = (ROOT / "scripts" / "verify-package.ps1").read_text(encoding="utf-8")
    assert "frontend/dist" in spec and "third-party/ffmpeg" in spec and "models/asr" in spec
    assert "collect_submodules(\"blueframe\")" in spec and "resource-manifest.json" in spec
    assert "3.11" in build and "PyInstaller" in build and "npm" in build
    assert "--smoke" in verify and "resource-manifest.json" in verify
