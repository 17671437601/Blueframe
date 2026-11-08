from blueframe.asr.models import AsrLine
from blueframe.drama.chunking import chunk_transcript


def test_chunking_overlaps_context_but_keeps_monotonic_source_ranges() -> None:
    lines = tuple(
        AsrLine(index=index, start_ms=index * 1000, end_ms=(index + 1) * 1000, text=f"第{index}句剧情")
        for index in range(6)
    )
    chunks = chunk_transcript(lines, max_characters=16, overlap_lines=1)

    assert len(chunks) >= 3
    assert all(chunk.start_ms < chunk.end_ms for chunk in chunks)
    assert all(
        chunks[index].context_line_indexes[-1]
        == chunks[index + 1].context_line_indexes[0]
        for index in range(len(chunks) - 1)
    )
    assert sorted({index for chunk in chunks for index in chunk.owned_line_indexes}) == list(range(6))
