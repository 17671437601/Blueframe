import pytest
from pydantic import ValidationError

from blueframe.editing.models import EditPlan, EditSegment, PlanKind
from blueframe.editing.normalize import normalize_segments, plan_similarity


def segment(source="s1", start=1000, end=4000, duration=10_000):
    return EditSegment(
        source_id=source, source_start_ms=start, source_end_ms=end,
        source_duration_ms=duration,
    )


def test_segments_enforce_source_bounds_and_minimum_duration() -> None:
    with pytest.raises(ValidationError):
        segment(start=9000, end=10_001)
    with pytest.raises(ValidationError):
        EditPlan(
            id="p", project_id="project", version=1, title="bad", kind=PlanKind.HIGHLIGHT,
            target_duration_ms=5000, segments=(segment(start=0, end=300),),
        )


def test_normalization_protects_edges_merges_adjacency_and_caps_target() -> None:
    normalized = normalize_segments(
        (
            segment(start=0, end=2500),
            segment(start=2600, end=5000),
            segment(source="s2", start=1000, end=6000),
        ),
        target_duration_ms=7000,
        protected_head_ms=500,
        protected_tail_ms=500,
        merge_gap_ms=200,
    )
    assert normalized[0].source_start_ms == 500
    assert normalized[0].source_end_ms == 5000
    assert sum(item.duration_ms for item in normalized) == 7000


def test_similarity_uses_source_time_coverage_not_titles() -> None:
    first = (segment(start=1000, end=4000), segment(source="s2", start=0, end=2000))
    near_duplicate = (segment(start=1100, end=3900), segment(source="s2", start=0, end=2000))
    diverse = (segment(source="s3", start=5000, end=8000),)
    assert plan_similarity(first, near_duplicate) > 0.8
    assert plan_similarity(first, diverse) == 0
