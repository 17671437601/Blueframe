from __future__ import annotations

from pathlib import Path

from blueframe.variants.models import VariantRecipe


def build_variant_command(ffmpeg: Path, source: Path, output: Path, recipe: VariantRecipe, *, overlay_path: Path | None = None, has_audio: bool = True) -> list[str]:
    if recipe.overlay_asset_id and overlay_path is None:
        raise ValueError("variant recipe requires its licensed overlay asset")
    command = [str(ffmpeg), "-hide_banner", "-nostdin", "-y", "-i", str(source)]
    filters = [
        f"[0:v:0]scale={recipe.width}:{recipe.height}:force_original_aspect_ratio=increase,"
        f"crop={recipe.width}:{recipe.height},"
        f"eq=saturation={recipe.saturation}:brightness={recipe.brightness},"
        f"setpts=PTS/{recipe.speed}[vbase]",
        (f"[0:a:0]atempo={recipe.speed},volume={recipe.audio_gain_db}dB,aresample=48000[aout]"
         if has_audio else "anullsrc=r=48000:cl=stereo,asetpts=N/SR/TB[aout]"),
    ]
    video_label = "vbase"
    if overlay_path is not None:
        command.extend(["-loop", "1", "-i", str(overlay_path)])
        filters.extend([
            f"[1:v:0]scale='min(iw,{recipe.width // 4})':-1[badge]",
            "[vbase][badge]overlay=W-w-24:H-h-24:format=auto[vout]",
        ])
        video_label = "vout"
    command.extend([
        "-filter_complex", ";".join(filters), "-map", f"[{video_label}]", "-map", "[aout]",
        "-c:v", "libx264", "-preset", "medium", "-b:v", recipe.video_bitrate,
        "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart",
        "-shortest", "-progress", "pipe:1", "-nostats", str(output),
    ])
    return command
