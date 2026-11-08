from pathlib import Path

from blueframe.rendering.graph import (
    RenderInput,
    RenderSegment,
    RenderSpec,
    build_render_commands,
    escape_subtitle_filter_path,
)


def test_builder_uses_argument_arrays_and_normalizes_mixed_media() -> None:
    spec = RenderSpec(
        ffmpeg=Path("C:/ffmpeg.exe"), output=Path("C:/输出/final.mp4"),
        width=1080, height=1920, fps=30,
        inputs=(
            RenderInput(source_id="s1", path=Path("C:/素材/横屏 one.mp4"), has_audio=True, rotation=90),
            RenderInput(source_id="s2", path=Path("C:/素材/silent.mp4"), has_audio=False),
        ),
        segments=(
            RenderSegment(source_id="s1", start_ms=1000, end_ms=3000),
            RenderSegment(source_id="s2", start_ms=0, end_ms=2000),
        ),
    )
    hardware, software = build_render_commands(spec, hardware_encoder="h264_nvenc")

    assert isinstance(hardware, list) and all(isinstance(item, str) for item in hardware)
    assert "shell=True" not in " ".join(hardware)
    graph = hardware[hardware.index("-filter_complex") + 1]
    assert "transpose=clock" in graph
    assert "scale=1080:1920:force_original_aspect_ratio=decrease" in graph
    assert "anullsrc=r=48000:cl=stereo" in graph
    assert "concat=n=2:v=1:a=1" in graph
    assert hardware[hardware.index("-c:v") + 1] == "h264_nvenc"
    assert software[software.index("-c:v") + 1] == "libx264"
    assert hardware[-1] == "C:\\输出\\final.mp4"


def test_subtitle_filter_escapes_windows_path_quotes_and_backslashes() -> None:
    escaped = escape_subtitle_filter_path(Path("C:/项目/O'Brien\\字幕.srt"))
    assert escaped == "C\\:/项目/O\\'Brien/字幕.srt"


def test_subtitle_stage_is_added_after_concat() -> None:
    spec = RenderSpec(
        ffmpeg=Path("ffmpeg"), output=Path("out.mp4"), width=1920, height=1080, fps=25,
        inputs=(RenderInput(source_id="s", path=Path("in.mp4"), has_audio=True),),
        segments=(RenderSegment(source_id="s", start_ms=0, end_ms=1000),),
        subtitle_path=Path("C:/字幕/成片.srt"),
    )
    command, _ = build_render_commands(spec)
    graph = command[command.index("-filter_complex") + 1]
    assert "[vbase]subtitles=filename='C\\:/字幕/成片.srt'[vout]" in graph
