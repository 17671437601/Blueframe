import json
from pathlib import Path

import pytest

from blueframe_desktop.resources import ResourceIntegrityError, create_manifest, discover_runtime_resources


def _layout(root: Path) -> None:
    (root / "third-party" / "ffmpeg" / "bin").mkdir(parents=True)
    (root / "third-party" / "ffmpeg" / "bin" / "ffmpeg.exe").write_bytes(b"ffmpeg")
    (root / "third-party" / "ffmpeg" / "bin" / "ffprobe.exe").write_bytes(b"ffprobe")
    for name in ("asr", "vad", "punc"):
        model = root / "models" / name; model.mkdir(parents=True)
        (model / "configuration.json").write_text(json.dumps({"model": name}), encoding="utf-8")
        (model / "model.pt").write_bytes(name.encode())


def test_discovers_tools_and_offline_models_from_verified_manifest(tmp_path: Path) -> None:
    _layout(tmp_path)
    manifest = create_manifest(tmp_path, [
        "third-party/ffmpeg/bin/ffmpeg.exe", "third-party/ffmpeg/bin/ffprobe.exe",
        "models/asr/configuration.json", "models/asr/model.pt",
        "models/vad/configuration.json", "models/vad/model.pt",
        "models/punc/configuration.json", "models/punc/model.pt",
    ])
    (tmp_path / "resource-manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

    resources = discover_runtime_resources(base_dir=tmp_path)

    assert resources.ffmpeg.name == "ffmpeg.exe"
    assert resources.asr_model == tmp_path / "models" / "asr"
    assert resources.vad_model == tmp_path / "models" / "vad"
    assert resources.punctuation_model == tmp_path / "models" / "punc"


def test_rejects_tampered_signed_resource_manifest(tmp_path: Path) -> None:
    _layout(tmp_path)
    manifest = create_manifest(tmp_path, ["third-party/ffmpeg/bin/ffmpeg.exe"])
    (tmp_path / "resource-manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    (tmp_path / "third-party" / "ffmpeg" / "bin" / "ffmpeg.exe").write_bytes(b"tampered")

    with pytest.raises(ResourceIntegrityError, match="integrity"):
        discover_runtime_resources(base_dir=tmp_path)
