from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Callable

from blueframe.assets.models import AssetDraft, AssetType, StorageOwnership


_EXTENSIONS = {
    AssetType.VIDEO: {".mp4", ".mov", ".mkv", ".avi", ".webm"},
    AssetType.AUDIO: {".mp3", ".wav", ".flac", ".m4a", ".aac"},
    AssetType.IMAGE: {".png", ".jpg", ".jpeg", ".webp", ".gif"},
    AssetType.FONT: {".ttf", ".otf", ".woff", ".woff2"},
}


class AssetScanner:
    def __init__(self, media_validator: Callable[[Path, AssetType], dict] | None = None) -> None:
        self.media_validator = media_validator or _basic_validate

    def scan(self, path: Path, *, origin: str, license_name: str, ownership: StorageOwnership) -> AssetDraft:
        path = path.resolve()
        if not origin.strip(): raise ValueError("asset origin is required")
        if not license_name.strip(): raise ValueError("asset license is required")
        if not path.is_file() or path.stat().st_size <= 0: raise ValueError("asset file is unavailable or empty")
        asset_type = next((kind for kind, extensions in _EXTENSIONS.items() if path.suffix.lower() in extensions), None)
        if asset_type is None: raise ValueError("unsupported asset type")
        metadata = self.media_validator(path, asset_type)
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b""): digest.update(block)
        return AssetDraft(
            sha256=digest.hexdigest(), asset_type=asset_type, path=path,
            origin=origin.strip(), license_name=license_name.strip(), ownership=ownership,
            metadata={**metadata, "size_bytes": path.stat().st_size, "filename": path.name},
        )


def _basic_validate(path: Path, asset_type: AssetType) -> dict:
    header = path.read_bytes()[:16]
    if asset_type is AssetType.IMAGE:
        valid = header.startswith(b"\x89PNG\r\n\x1a\n") or header.startswith(b"\xff\xd8\xff") or header[:6] in {b"GIF87a", b"GIF89a"} or header.startswith(b"RIFF")
        if not valid: raise ValueError("invalid image asset")
    elif asset_type is AssetType.FONT:
        if not (header.startswith((b"\x00\x01\x00\x00", b"OTTO", b"wOFF", b"wOF2"))): raise ValueError("invalid font asset")
    return {}
