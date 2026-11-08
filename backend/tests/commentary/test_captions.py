from pathlib import Path

from blueframe.commentary.captions import escape_ass_text, write_contextual_ass
from blueframe.commentary.voice import VoiceEntry, VoiceTimeline
from blueframe.commentary.models import SourceCitation


def test_ass_caption_escapes_unicode_braces_backslashes_and_newlines(tmp_path: Path) -> None:
    citation = SourceCitation(source_id="s", start_ms=0, end_ms=1000, quote="原话{重要}\\下一行")
    timeline = VoiceTimeline(
        narration_path=tmp_path / "voice.mp3", duration_ms=1500,
        entries=(VoiceEntry(sentence_index=0, text="解说，第一行\n第二行", start_ms=0, end_ms=1500, citations=(citation,)),),
    )
    output = tmp_path / "字幕.ass"
    write_contextual_ass(timeline, output, width=1080, height=1920)
    content = output.read_text("utf-8")
    assert "Style: Context" in content and "Style: Narration" in content
    assert "\\{重要\\}" in content
    assert "\\\\下一行" in content
    assert "第一行\\N第二行" in content
    assert escape_ass_text("a{b}") == "a\\{b\\}"
