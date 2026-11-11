from __future__ import annotations

from pathlib import Path
from typing import Mapping, Sequence

from blueframe.asr.models import AsrLine
from blueframe.commentary.captions import escape_ass_text
from blueframe.story.models import StorySegmentSpec


def write_story_ass(
    segments: Sequence[StorySegmentSpec],
    lines_by_source: Mapping[str, Sequence[AsrLine]],
    output: Path,
    *,
    width: int,
    height: int,
) -> Path:
    output.parent.mkdir(parents=True, exist_ok=True)
    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {width}
PlayResY: {height}
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name,Fontname,Fontsize,PrimaryColour,SecondaryColour,OutlineColour,BackColour,Bold,Italic,Underline,StrikeOut,ScaleX,ScaleY,Spacing,Angle,BorderStyle,Outline,Shadow,Alignment,MarginL,MarginR,MarginV,Encoding
Style: Story,Microsoft YaHei,{max(28, height // 32)},&H00FFFFFF,&H00FFFFFF,&H90000000,&H90000000,-1,0,0,0,100,100,0,0,1,2,1,2,80,80,{max(48, height // 10)},1

[Events]
Format: Layer,Start,End,Style,Name,MarginL,MarginR,MarginV,Effect,Text
"""
    events: list[str] = []
    offset = 0
    for segment in segments:
        for line in lines_by_source.get(segment.source_id, ()):
            start = max(line.start_ms, segment.start_ms)
            end = min(line.end_ms, segment.end_ms)
            if end - start < 120:
                continue
            events.append(
                f"Dialogue: 0,{_ass_time(offset + start - segment.start_ms)},"
                f"{_ass_time(offset + end - segment.start_ms)},"
                f"Story,,0,0,0,,{escape_ass_text(line.text)}"
            )
        offset += segment.end_ms - segment.start_ms
    output.write_text(header + "\n".join(events) + "\n", encoding="utf-8-sig")
    return output


def _ass_time(milliseconds: int) -> str:
    centiseconds = max(0, milliseconds) // 10
    hours, remainder = divmod(centiseconds, 360_000)
    minutes, remainder = divmod(remainder, 6_000)
    seconds, centiseconds = divmod(remainder, 100)
    return f"{hours}:{minutes:02d}:{seconds:02d}.{centiseconds:02d}"
