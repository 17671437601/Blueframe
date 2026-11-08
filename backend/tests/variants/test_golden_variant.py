import subprocess
from pathlib import Path

import pytest

from blueframe.media.probe import probe_media
from blueframe.media.tools import discover_executables
from blueframe.variants.graph import build_variant_command
from blueframe.variants.models import VariantRecipe


def test_real_ffmpeg_renders_playable_variant(tmp_path: Path) -> None:
    repository_root = Path(__file__).resolve().parents[4]
    try: tools = discover_executables(search_roots=[repository_root])
    except FileNotFoundError: pytest.skip("bundled FFmpeg is unavailable")
    source, output = tmp_path / "master.mp4", tmp_path / "variant.mp4"
    subprocess.run([
        str(tools.ffmpeg), "-hide_banner", "-loglevel", "error", "-y",
        "-f", "lavfi", "-i", "color=c=blue:s=640x360:d=1",
        "-f", "lavfi", "-i", "sine=frequency=440:duration=1", "-shortest",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", str(source),
    ], check=True)
    recipe = VariantRecipe(seed=1, width=360, height=640, saturation=1.02, brightness=0.01, speed=1.03, audio_gain_db=-2, video_bitrate="1M")
    subprocess.run(build_variant_command(tools.ffmpeg, source, output, recipe), check=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    info = probe_media(output, tools)
    assert (info.width, info.height, info.has_audio) == (360, 640, True)
    assert 800 <= info.duration_ms <= 1200
