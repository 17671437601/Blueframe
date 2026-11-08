from pathlib import Path

import pytest
from pydantic import ValidationError

from blueframe.variants.models import VariantRecipe, generate_recipe
from blueframe.variants.graph import build_variant_command


def test_same_seed_and_index_produce_identical_bounded_recipe() -> None:
    first = generate_recipe(seed=42, index=3, width=1080, height=1920)
    second = generate_recipe(seed=42, index=3, width=1080, height=1920)
    assert first == second
    assert first.width % 2 == first.height % 2 == 0
    assert -6 <= first.audio_gain_db <= 3
    assert 0.94 <= first.speed <= 1.06


def test_recipe_rejects_invalid_dimensions_or_inaudible_audio() -> None:
    with pytest.raises(ValidationError):
        VariantRecipe(seed=1, width=1079, height=1920, saturation=1, brightness=0, speed=1, audio_gain_db=0, video_bitrate="8M")
    with pytest.raises(ValidationError):
        VariantRecipe(seed=1, width=1080, height=1920, saturation=1, brightness=0, speed=1, audio_gain_db=-30, video_bitrate="8M")


def test_variant_command_is_argument_array_with_synchronized_speed(tmp_path: Path) -> None:
    recipe = VariantRecipe(seed=7, width=720, height=1280, saturation=1.05, brightness=0.02, speed=1.03, audio_gain_db=-2, video_bitrate="5M")
    command = build_variant_command(Path("ffmpeg"), tmp_path / "主成片.mp4", tmp_path / "变体.mp4", recipe)
    graph = command[command.index("-filter_complex") + 1]
    assert all(isinstance(item, str) for item in command)
    assert "setpts=PTS/1.03" in graph and "atempo=1.03" in graph
    assert "scale=720:1280:force_original_aspect_ratio=increase" in graph
    assert command[-1].endswith("变体.mp4")
