from __future__ import annotations

from blueframe.drama.models import StoryAnalysis


def story_analysis_schema() -> dict:
    return StoryAnalysis.model_json_schema()
