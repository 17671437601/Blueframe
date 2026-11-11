from pathlib import Path

from blueframe.asr.models import AsrLine
from blueframe.highlights.captions import write_clip_ass


def test_clip_ass_is_shifted_to_clip_start_and_clipped(tmp_path: Path) -> None:
    lines = (
        AsrLine(index=0, start_ms=4_500, end_ms=6_000, text="上一句"),
        AsrLine(index=1, start_ms=6_200, end_ms=8_000, text="片段内第一句"),
        AsrLine(index=2, start_ms=9_500, end_ms=11_400, text="跨越结尾"),
        AsrLine(index=3, start_ms=12_000, end_ms=13_000, text="片段外"),
    )

    output = write_clip_ass(
        lines, tmp_path / "clip.ass",
        clip_start_ms=5_000, clip_end_ms=11_000, width=1080, height=1920,
    )

    text = output.read_text(encoding="utf-8-sig")
    assert "PlayResX: 1080" in text
    assert "0:00:00.00,0:00:01.00,Clip" in text
    assert "0:00:01.20,0:00:03.00,Clip" in text
    assert "0:00:04.50,0:00:06.00,Clip" in text
    assert "上一句" in text
    assert "片段外" not in text
