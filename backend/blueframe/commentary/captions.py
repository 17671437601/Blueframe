from __future__ import annotations

from pathlib import Path

from blueframe.commentary.voice import VoiceTimeline


def write_contextual_ass(timeline: VoiceTimeline, output: Path, *, width: int, height: int) -> Path:
    output.parent.mkdir(parents=True, exist_ok=True)
    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {width}
PlayResY: {height}
WrapStyle: 2

[V4+ Styles]
Format: Name,Fontname,Fontsize,PrimaryColour,SecondaryColour,OutlineColour,BackColour,Bold,Italic,Underline,StrikeOut,ScaleX,ScaleY,Spacing,Angle,BorderStyle,Outline,Shadow,Alignment,MarginL,MarginR,MarginV,Encoding
Style: Context,Microsoft YaHei,{max(24, height // 42)},&H00EAF2FF,&H00FFFFFF,&H90000000,&H70000000,0,0,0,0,100,100,0,0,3,1,0,8,60,60,{height // 12},1
Style: Narration,Microsoft YaHei,{max(32, height // 32)},&H00FFFFFF,&H00FFFFFF,&H90000000,&H800B2455,-1,0,0,0,100,100,0,0,3,2,0,2,70,70,{height // 10},1

[Events]
Format: Layer,Start,End,Style,Name,MarginL,MarginR,MarginV,Effect,Text
"""
    events: list[str] = []
    for entry in timeline.entries:
        start, end = _ass_time(entry.start_ms), _ass_time(entry.end_ms)
        context = " / ".join(dict.fromkeys(citation.quote for citation in entry.citations))
        if context:
            events.append(f"Dialogue: 0,{start},{end},Context,,0,0,0,,{escape_ass_text(context)}")
        events.append(f"Dialogue: 1,{start},{end},Narration,,0,0,0,,{escape_ass_text(entry.text)}")
    output.write_text(header + "\n".join(events) + "\n", encoding="utf-8-sig")
    return output


def escape_ass_text(value: str) -> str:
    return value.replace("\\", "\\\\").replace("{", "\\{").replace("}", "\\}").replace("\r\n", "\\N").replace("\n", "\\N").replace("\r", "\\N")


def _ass_time(milliseconds: int) -> str:
    centiseconds = milliseconds // 10
    hours, remainder = divmod(centiseconds, 360_000)
    minutes, remainder = divmod(remainder, 6_000)
    seconds, centiseconds = divmod(remainder, 100)
    return f"{hours}:{minutes:02d}:{seconds:02d}.{centiseconds:02d}"
