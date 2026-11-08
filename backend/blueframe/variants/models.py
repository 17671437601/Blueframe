from __future__ import annotations

import hashlib
import random

from pydantic import Field, field_validator

from blueframe.domain.common import DomainModel


class VariantRecipe(DomainModel):
    recipe_version: str = "variant-v1"
    seed: int = Field(ge=0, le=2**63 - 1)
    width: int = Field(ge=320, le=3840)
    height: int = Field(ge=320, le=3840)
    saturation: float = Field(ge=0.8, le=1.2)
    brightness: float = Field(ge=-0.1, le=0.1)
    speed: float = Field(ge=0.9, le=1.1)
    audio_gain_db: float = Field(ge=-12, le=6)
    video_bitrate: str = Field(pattern=r"^[1-9][0-9]*(?:k|M)$")
    overlay_asset_id: str | None = None

    @field_validator("width", "height")
    @classmethod
    def even_dimensions(cls, value: int) -> int:
        if value % 2: raise ValueError("variant dimensions must be even")
        return value


def generate_recipe(*, seed: int, index: int, width: int, height: int, overlay_asset_id: str | None = None) -> VariantRecipe:
    if index < 0: raise ValueError("variant index must be non-negative")
    material = hashlib.sha256(f"{seed}:{index}:variant-v1".encode()).digest()
    generator = random.Random(int.from_bytes(material[:8], "big"))
    return VariantRecipe(
        seed=seed, width=width, height=height,
        saturation=round(generator.uniform(0.94, 1.06), 3),
        brightness=round(generator.uniform(-0.025, 0.025), 3),
        speed=round(generator.uniform(0.94, 1.06), 3),
        audio_gain_db=round(generator.uniform(-6, 3), 2),
        video_bitrate=generator.choice(("5M", "6M", "8M")),
        overlay_asset_id=overlay_asset_id,
    )
