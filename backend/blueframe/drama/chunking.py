from __future__ import annotations

from pydantic import Field

from blueframe.asr.models import AsrLine
from blueframe.domain.common import DomainModel


class TranscriptChunk(DomainModel):
    index: int = Field(ge=0)
    start_ms: int = Field(ge=0)
    end_ms: int = Field(gt=0)
    text: str = Field(min_length=1)
    context_line_indexes: tuple[int, ...]
    owned_line_indexes: tuple[int, ...]


def chunk_transcript(
    lines: tuple[AsrLine, ...],
    *,
    max_characters: int = 12_000,
    overlap_lines: int = 2,
) -> tuple[TranscriptChunk, ...]:
    if max_characters < 1 or overlap_lines < 0:
        raise ValueError("invalid chunk settings")
    chunks: list[TranscriptChunk] = []
    cursor = 0
    while cursor < len(lines):
        end = cursor
        characters = 0
        while end < len(lines):
            line_size = len(lines[end].text) + 24
            if end > cursor and characters + line_size > max_characters:
                break
            characters += line_size
            end += 1
        context_start = max(0, cursor - overlap_lines) if cursor else 0
        context = lines[context_start:end]
        chunks.append(
            TranscriptChunk(
                index=len(chunks),
                start_ms=context[0].start_ms,
                end_ms=context[-1].end_ms,
                text="\n".join(
                    f"[{line.start_ms}-{line.end_ms}] {line.text}" for line in context
                ),
                context_line_indexes=tuple(line.index for line in context),
                owned_line_indexes=tuple(line.index for line in lines[cursor:end]),
            )
        )
        cursor = end
    return tuple(chunks)
