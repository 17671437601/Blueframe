from pathlib import Path

import pytest

from blueframe.assets.models import AssetDraft, AssetType, StorageOwnership
from blueframe.assets.repository import AssetRepository
from blueframe.assets.scanner import AssetScanner


def test_scanner_fingerprints_supported_assets_and_requires_license(tmp_path: Path) -> None:
    image = tmp_path / "海报.png"; image.write_bytes(b"\x89PNG\r\n\x1a\nfixture")
    scanner = AssetScanner(media_validator=lambda _path, _type: {"width": 100, "height": 200})
    draft = scanner.scan(image, origin="用户导入", license_name="CC-BY", ownership=StorageOwnership.LINKED)
    assert draft.asset_type is AssetType.IMAGE
    assert len(draft.sha256) == 64
    assert draft.metadata["width"] == 100
    with pytest.raises(ValueError, match="license"):
        scanner.scan(image, origin="用户导入", license_name="", ownership=StorageOwnership.LINKED)


def test_repository_is_content_addressed_and_marks_moved_file_unavailable(migrated_session_factory, tmp_path: Path) -> None:
    source = tmp_path / "music.mp3"; source.write_bytes(b"ID3fixture")
    draft = AssetDraft(
        sha256="a" * 64, asset_type=AssetType.AUDIO, path=source,
        origin="自有录音", license_name="版权所有者授权", ownership=StorageOwnership.LINKED,
        metadata={"duration_ms": 1000},
    )
    repository = AssetRepository(migrated_session_factory)
    first = repository.save(draft)
    duplicate = repository.save(draft)
    source.rename(tmp_path / "moved.mp3")
    unavailable = repository.refresh_availability(first.id)
    assert duplicate.id == first.id
    assert unavailable.available is False
    assert repository.get(first.id).sha256 == "a" * 64
