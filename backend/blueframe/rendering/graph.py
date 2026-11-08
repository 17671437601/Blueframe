from __future__ import annotations

from pathlib import Path

from pydantic import Field, model_validator

from blueframe.domain.common import DomainModel


class RenderInput(DomainModel):
    source_id: str = Field(min_length=1)
    path: Path
    has_audio: bool
    rotation: int = 0


class RenderSegment(DomainModel):
    source_id: str = Field(min_length=1)
    start_ms: int = Field(ge=0)
    end_ms: int = Field(gt=0)

    @model_validator(mode="after")
    def valid_range(self) -> "RenderSegment":
        if self.end_ms <= self.start_ms:
            raise ValueError("render segment end must be after start")
        return self


class RenderSpec(DomainModel):
    ffmpeg: Path
    output: Path
    width: int = Field(gt=0)
    height: int = Field(gt=0)
    fps: int = Field(ge=1, le=120)
    inputs: tuple[RenderInput, ...] = Field(min_length=1)
    segments: tuple[RenderSegment, ...] = Field(min_length=1)
    subtitle_path: Path | None = None
    narration_path: Path | None = None
    video_bitrate: str = "8M"
    audio_bitrate: str = "192k"

    @model_validator(mode="after")
    def known_sources(self) -> "RenderSpec":
        ids = {item.source_id for item in self.inputs}
        if len(ids) != len(self.inputs):
            raise ValueError("render input source ids must be unique")
        if any(segment.source_id not in ids for segment in self.segments):
            raise ValueError("render segment references an unknown source")
        return self


def build_render_commands(
    spec: RenderSpec, *, hardware_encoder: str | None = None
) -> tuple[list[str], list[str]]:
    source_indexes = {item.source_id: index for index, item in enumerate(spec.inputs)}
    arguments = [str(spec.ffmpeg), "-hide_banner", "-nostdin", "-y"]
    for item in spec.inputs:
        arguments.extend(["-i", str(item.path)])
    narration_index = len(spec.inputs)
    if spec.narration_path is not None:
        arguments.extend(["-i", str(spec.narration_path)])

    filters: list[str] = []
    concat_inputs: list[str] = []
    for index, segment in enumerate(spec.segments):
        input_index = source_indexes[segment.source_id]
        source = spec.inputs[input_index]
        start = _seconds(segment.start_ms)
        end = _seconds(segment.end_ms)
        duration = _seconds(segment.end_ms - segment.start_ms)
        video_filters = [
            f"trim=start={start}:end={end}",
            "setpts=PTS-STARTPTS",
        ]
        if source.rotation == 90:
            video_filters.append("transpose=clock")
        elif source.rotation == 270:
            video_filters.append("transpose=cclock")
        elif source.rotation == 180:
            video_filters.extend(["hflip", "vflip"])
        video_filters.extend(
            [
                f"scale={spec.width}:{spec.height}:force_original_aspect_ratio=decrease",
                f"pad={spec.width}:{spec.height}:(ow-iw)/2:(oh-ih)/2:color=black",
                "setsar=1",
                f"fps={spec.fps}",
                "format=yuv420p",
            ]
        )
        filters.append(f"[{input_index}:v:0]{','.join(video_filters)}[v{index}]")
        if source.has_audio:
            filters.append(
                f"[{input_index}:a:0]atrim=start={start}:end={end},"
                f"asetpts=PTS-STARTPTS,aresample=48000:async=1:first_pts=0[a{index}]"
            )
        else:
            filters.append(
                f"anullsrc=r=48000:cl=stereo,atrim=duration={duration},"
                f"asetpts=PTS-STARTPTS[a{index}]"
            )
        concat_inputs.append(f"[v{index}][a{index}]")
    video_label = "vbase" if spec.subtitle_path else "vout"
    audio_label = "abase" if spec.narration_path is not None else "aout"
    filters.append(
        f"{''.join(concat_inputs)}concat=n={len(spec.segments)}:v=1:a=1"
        f"[{video_label}][{audio_label}]"
    )
    if spec.narration_path is not None:
        duration = _seconds(sum(item.end_ms - item.start_ms for item in spec.segments))
        filters.append(f"[abase]volume=0.25[abed]")
        filters.append(f"[{narration_index}:a:0]aresample=48000,apad,atrim=duration={duration}[narr]")
        filters.append("[abed][narr]amix=inputs=2:duration=first:dropout_transition=0[aout]")
    if spec.subtitle_path:
        escaped = escape_subtitle_filter_path(spec.subtitle_path)
        filters.append(f"[vbase]subtitles=filename='{escaped}'[vout]")

    base = arguments + [
        "-filter_complex", ";".join(filters),
        "-map", "[vout]", "-map", "[aout]",
    ]
    common = [
        "-b:v", spec.video_bitrate, "-c:a", "aac", "-b:a", spec.audio_bitrate,
        "-movflags", "+faststart", "-progress", "pipe:1", "-nostats", str(spec.output),
    ]
    software = base + ["-c:v", "libx264", "-preset", "medium"] + common
    primary = (
        base + ["-c:v", hardware_encoder, "-preset", "p4"] + common
        if hardware_encoder
        else software.copy()
    )
    return primary, software


def escape_subtitle_filter_path(path: Path) -> str:
    value = str(path).replace("\\", "/")
    return value.replace(":", r"\:").replace("'", r"\'")


def _seconds(milliseconds: int) -> str:
    return f"{milliseconds / 1000:.3f}".rstrip("0").rstrip(".")
