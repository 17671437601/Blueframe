from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import json
import yaml
from jsonschema import Draft202012Validator


REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
INVENTORY_PATH = REPOSITORY_ROOT / "evidence" / "legacy_behavior_inventory.yaml"
SCHEMA_PATH = REPOSITORY_ROOT / "evidence" / "schemas" / "legacy_behavior.schema.json"
REQUIRED_FEATURES = {
    "workbench",
    "drama_production",
    "movie_commentary",
    "video_variants",
    "live_clipping",
    "asset_center",
    "task_center",
    "settings",
}
SENSITIVE_KEY = re.compile(r"token|cookie|password|secret|authorization", re.IGNORECASE)


def _walk_keys(value: Any) -> list[str]:
    if isinstance(value, dict):
        keys = [str(key) for key in value]
        for child in value.values():
            keys.extend(_walk_keys(child))
        return keys
    if isinstance(value, list):
        keys: list[str] = []
        for child in value:
            keys.extend(_walk_keys(child))
        return keys
    return []


def test_inventory_is_schema_valid_and_redacted() -> None:
    assert INVENTORY_PATH.is_file(), "legacy behavior inventory must exist"
    assert SCHEMA_PATH.is_file(), "legacy behavior schema must exist"

    inventory = yaml.safe_load(INVENTORY_PATH.read_text(encoding="utf-8"))
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    Draft202012Validator(schema).validate(inventory)

    observed_features = {record["feature"] for record in inventory["records"]}
    assert REQUIRED_FEATURES <= observed_features

    sensitive_keys = [key for key in _walk_keys(inventory) if SENSITIVE_KEY.search(key)]
    assert sensitive_keys == [], f"inventory contains sensitive keys: {sensitive_keys}"
