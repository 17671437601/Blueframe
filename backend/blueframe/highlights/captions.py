from __future__ import annotations

from pathlib import Path
from typing import Sequence

from blueframe.asr.models import AsrLine
from blueframe.commentary.captions import escape_ass_text


def write_clip_ass(
    lines: Sequence[AsrLine],
    output: Path,
    *,
    clip_start_ms: int,
    clip_end_ms: int,
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
Style: Clip,Microsoft YaHei,{max(28, height // 32)},&H00FFFFFF,&H00FFFFFF,&H90000000,&H90000000,-1,0,0,0,100,100,0,0,1,2,1,2,80,80,{max(48, height // 10)},1

[Events]
Format: Layer,Start,End,Style,Name,MarginL,MarginR,MarginV,Effect,Text
"""
    events: list[str] = []
    for line in lines:
        start = max(line.start_ms, clip_start_ms)
        end = min(line.end_ms, clip_end_ms)
        if end - start < 120:
            continue
        events.append(
            f"Dialogue: 0,{_ass_time(start - clip_start_ms)},{_ass_time(end - clip_start_ms)},"
            f"Clip,,0,0,0,,{escape_ass_text(line.text)}"
        )
    output.write_text(header + "\n".join(events) + "\n", encoding="utf-8-sig")
    return output


def _ass_time(milliseconds: int) -> str:
    centiseconds = max(0, milliseconds) // 10
    hours, remainder = divmod(centiseconds, 360_000)
    minutes, remainder = divmod(remainder, 6_000)
    seconds, centiseconds = divmod(remainder, 100)
    return f"{hours}:{minutes:02d}:{seconds:02d}.{centiseconds:02d}"
