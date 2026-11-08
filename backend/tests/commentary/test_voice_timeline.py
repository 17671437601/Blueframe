from datetime import UTC, datetime
from pathlib import Path

from blueframe.commentary.models import CommentaryScriptVersion, CommentarySentence, SourceCitation
from blueframe.commentary.voice import VoiceTimelineService, split_for_tts
from blueframe.domain.common import ProviderUsage
from blueframe.providers.tts import TtsResult


class FakeTts:
    def __init__(self): self.calls = []
    async def synthesize(self, request):
        self.calls.append(request)
        request.output_root.mkdir(parents=True, exist_ok=True)
        output = request.output_root / request.filename
        output.write_bytes(b"audio")
        return TtsResult(provider="fixture", audio_path=output, duration_ms=len(request.text) * 100, usage=ProviderUsage(input_units=1, output_units=1))


class FakeAssembler:
    def __init__(self): self.inputs = []
    def assemble(self, inputs, output):
        self.inputs = list(inputs); output.write_bytes(b"joined")


def script(text: str) -> CommentaryScriptVersion:
    citation = SourceCitation(source_id="source-a", start_ms=0, end_ms=1000, quote="原始对白")
    return CommentaryScriptVersion(
        id="script-a", project_id="project-a", version=1, title="解说", voice="voice-a",
        prompt_version="v1", provider="fixture", model="m", created_at=datetime.now(UTC),
        sentences=(CommentarySentence(text=text, citations=(citation,)), CommentarySentence(text="结尾。", manual=True)),
    )


def test_sentence_splitter_preserves_unicode_and_provider_limit() -> None:
    text = "张三发现了线索，John 也看到了。随后，剧情继续推进！"
    parts = split_for_tts(text, max_characters=12)
    assert "".join(parts) == text
    assert all(0 < len(part) <= 12 for part in parts)


def test_voice_timeline_uses_actual_audio_durations_and_assembles_in_order(tmp_path: Path) -> None:
    tts, assembler = FakeTts(), FakeAssembler()
    timeline = VoiceTimelineService(tts, assembler, max_characters=6).synthesize(script("第一句很长，需要拆分。"), tmp_path)

    assert timeline.entries[0].start_ms == 0
    assert timeline.entries[1].start_ms == timeline.entries[0].end_ms
    assert timeline.duration_ms == sum(len(call.text) * 100 for call in tts.calls)
    assert assembler.inputs == [call.output_root / call.filename for call in tts.calls]
    assert timeline.narration_path.read_bytes() == b"joined"
