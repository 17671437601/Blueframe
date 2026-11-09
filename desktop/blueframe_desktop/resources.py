from __future__ import annotations

import hashlib
import hmac
import json
import sys
from dataclasses import dataclass
from pathlib import Path


_MANIFEST_KEY = b"blueframe-resource-manifest-v1"
_MODEL_NAMES = {
    "asr": "speech_seaco_paraformer_large_asr_nat-zh-cn-16k-common-vocab8404-pytorch",
    "vad": "speech_fsmn_vad_zh-cn-16k-common-pytorch",
    "punc": "punc_ct-transformer_zh-cn-common-vocab272727-pytorch",
}


class ResourceIntegrityError(RuntimeError): pass


@dataclass(frozen=True)
class RuntimeResources:
    root: Path
    ffmpeg: Path
    ffprobe: Path
    asr_model: Path
    vad_model: Path
    punctuation_model: Path
    verified: bool


def create_manifest(root: Path, relative_paths: list[str]) -> dict:
    return create_manifest_from_sources({relative: root / relative for relative in relative_paths})


def create_manifest_from_sources(sources: dict[str, Path]) -> dict:
    files = {relative.replace("\\", "/"): _sha256(source) for relative, source in sorted(sources.items())}
    body = {"format": "blueframe-resources-v1", "files": files}
    body["signature"] = hmac.new(_MANIFEST_KEY, _canonical(body), hashlib.sha256).hexdigest()
    return body


def discover_runtime_resources(*, base_dir: Path | None = None, repository_root: Path | None = None) -> RuntimeResources:
    if base_dir is not None:
        root = base_dir.resolve(); _verify_manifest(root)
        return _resources(root, "third-party/ffmpeg/bin", "models", verified=True)

    frozen = Path(getattr(sys, "_MEIPASS", Path(sys.executable).resolve().parent))
    if (frozen / "resource-manifest.json").is_file():
        _verify_manifest(frozen)
        return _resources(frozen, "third-party/ffmpeg/bin", "models", verified=True)

    if repository_root is None: raise ResourceIntegrityError("runtime resource root is unavailable")
    legacy = repository_root.resolve().parent
    model_root = legacy / "model" / "hub" / "iic"
    ffmpeg_root = legacy / "_internal" / "ffmpeg" / "bin"
    resources = RuntimeResources(
        legacy, ffmpeg_root / "ffmpeg.exe", ffmpeg_root / "ffprobe.exe",
        model_root / _MODEL_NAMES["asr"], model_root / _MODEL_NAMES["vad"], model_root / _MODEL_NAMES["punc"], False,
    )
    _require(resources)
    return resources


def _resources(root: Path, ffmpeg_dir: str, model_dir: str, *, verified: bool) -> RuntimeResources:
    ffmpeg_root, models = root / ffmpeg_dir, root / model_dir
    resources = RuntimeResources(
        root, ffmpeg_root / "ffmpeg.exe", ffmpeg_root / "ffprobe.exe",
        models / "asr", models / "vad", models / "punc", verified,
    )
    _require(resources); return resources


def _require(resources: RuntimeResources) -> None:
    required = (resources.ffmpeg, resources.ffprobe, resources.asr_model / "configuration.json",
                resources.vad_model / "configuration.json", resources.punctuation_model / "configuration.json")
    missing = [str(path) for path in required if not path.exists()]
    if missing: raise ResourceIntegrityError("required offline resource is missing: " + ", ".join(missing))


def _verify_manifest(root: Path) -> None:
    path = root / "resource-manifest.json"
    try: manifest = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error: raise ResourceIntegrityError("resource manifest is unavailable") from error
    signature = manifest.pop("signature", None)
    expected = hmac.new(_MANIFEST_KEY, _canonical(manifest), hashlib.sha256).hexdigest()
    if not isinstance(signature, str) or not hmac.compare_digest(signature, expected):
        raise ResourceIntegrityError("resource manifest signature is invalid")
    for relative, digest in manifest.get("files", {}).items():
        candidate = (root / relative).resolve()
        try: candidate.relative_to(root)
        except ValueError as error: raise ResourceIntegrityError("resource manifest path escaped package root") from error
        if not candidate.is_file() or not hmac.compare_digest(_sha256(candidate), str(digest)):
            raise ResourceIntegrityError(f"resource integrity check failed: {relative}")


def _canonical(value: dict) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""): digest.update(block)
    return digest.hexdigest()
