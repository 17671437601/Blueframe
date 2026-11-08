import pytest
from pydantic import ValidationError

from blueframe.asr.models import AsrDocument, AsrLine, AsrStatus


def test_asr_document_rejects_overlapping_or_reversed_lines() -> None:
    with pytest.raises(ValidationError):
        AsrLine(index=0, start_ms=200, end_ms=100, text="bad")

    with pytest.raises(ValidationError, match="overlap"):
        AsrDocument(
            id="doc", source_id="source", cache_key="key", model_version="v1",
            language="zh", duration_ms=1000, status=AsrStatus.COMPLETED,
            lines=(
                AsrLine(index=0, start_ms=0, end_ms=600, text="one"),
                AsrLine(index=1, start_ms=500, end_ms=900, text="two"),
            ),
        )
