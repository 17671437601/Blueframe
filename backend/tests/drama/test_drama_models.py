from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from blueframe.drama.models import (
    Character,
    Conflict,
    EdlCandidate,
    ExplosionCandidate,
    StoryAnalysis,
    StoryAnalysisVersion,
)
from blueframe.drama.schemas import story_analysis_schema


def analysis() -> StoryAnalysis:
    return StoryAnalysis(
        episode_summary="主角发现秘密并决定反击。",
        characters=(Character(name="林夏", role="主角", description="记者"),),
        conflicts=(Conflict(start_ms=1000, end_ms=5000, summary="身份暴露"),),
        explosions=(
            ExplosionCandidate(
                start_ms=2000,
                end_ms=4500,
                title="秘密揭开",
                reason="核心反转",
                score=92,
            ),
        ),
        edit_candidates=(
            EdlCandidate(
                title="高能版",
                rationale="突出反转",
                segments=((1000, 5000),),
            ),
        ),
        media_duration_ms=10_000,
    )


def test_analysis_schema_is_strict_and_domain_timeline_is_valid() -> None:
    model = analysis()
    schema = story_analysis_schema()
    assert schema["additionalProperties"] is False
    assert model.explosions[0].score == 92

    with pytest.raises(ValidationError):
        ExplosionCandidate(
            start_ms=0, end_ms=1000, title="bad", reason="bad", score=101
        )
    with pytest.raises(ValidationError, match="exceeds media duration"):
        StoryAnalysis.model_validate(
            {**analysis().model_dump(), "media_duration_ms": 3000}
        )


def test_analysis_versions_can_coexist_and_accepted_version_is_immutable() -> None:
    first = StoryAnalysisVersion(
        id="v1",
        project_id="p1",
        version=1,
        prompt_version="story-v1",
        provider="fixture",
        model="model-a",
        analysis=analysis(),
        accepted=True,
        created_at=datetime(2026, 11, 8, tzinfo=UTC),
    )
    second = first.model_copy(
        update={"id": "v2", "version": 2, "accepted": False, "model": "model-b"}
    )
    assert first.version == 1 and second.version == 2
    with pytest.raises(ValidationError):
        StoryAnalysisVersion.model_validate({**first.model_dump(), "version": 0})
