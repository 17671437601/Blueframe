from datetime import UTC, datetime

import pytest

from blueframe.drama.models import ExplosionCandidate, StoryAnalysis
from blueframe.projects.models import ProjectSource
from blueframe.story.planner import build_story_plans


def _source(source_id: str, order: int, duration_ms: int) -> ProjectSource:
    now = datetime.now(UTC)
    return ProjectSource(
        id=source_id,
        project_id="project",
        relative_path=f"{source_id}.mp4",
        order_index=order,
        size_bytes=1,
        modified_ns=1,
        content_fingerprint="fingerprint",
        media_info={"duration_ms": duration_ms, "has_audio": True, "rotation": 0},
        created_at=now,
        updated_at=now,
    )


def _analysis(explosions: tuple[ExplosionCandidate, ...], duration_ms: int) -> StoryAnalysis:
    return StoryAnalysis(
        episode_summary="整部剧的剧情摘要",
        explosions=explosions,
        media_duration_ms=duration_ms,
    )


def _explosion(start_ms: int, end_ms: int, score: int, title: str) -> ExplosionCandidate:
    return ExplosionCandidate(
        start_ms=start_ms, end_ms=end_ms, title=title, reason="冲突集中", score=score,
    )


def test_plans_hit_the_duration_window_and_keep_chronological_order() -> None:
    sources = (_source("ep1", 0, 300_000), _source("ep2", 1, 300_000))
    analysis = _analysis(
        tuple(
            _explosion(index * 40_000, index * 40_000 + 12_000, 95 - index, f"高光 {index}")
            for index in range(8)
        ),
        600_000,
    )

    plans = build_story_plans(
        analysis, sources, target_count=3, min_duration_ms=60_000, max_duration_ms=150_000,
    )

    assert len(plans) == 3
    for plan in plans:
        assert 60_000 * 0.9 <= plan.duration_ms <= 150_000 * 1.1
        by_source: dict[str, list[tuple[int, int]]] = {}
        for segment in plan.segments:
            by_source.setdefault(segment.source_id, []).append((segment.start_ms, segment.end_ms))
            assert segment.end_ms <= 300_000
        for ranges in by_source.values():
            assert ranges == sorted(ranges)
            assert all(
                later[0] >= earlier[1] for earlier, later in zip(ranges, ranges[1:], strict=False)
            )


def test_plans_differ_between_items() -> None:
    sources = (_source("ep1", 0, 300_000), _source("ep2", 1, 300_000))
    analysis = _analysis(
        tuple(
            _explosion(index * 30_000, index * 30_000 + 10_000, 90 - index % 5, f"高光 {index}")
            for index in range(10)
        ),
        600_000,
    )

    plans = build_story_plans(
        analysis, sources, target_count=3, min_duration_ms=90_000, max_duration_ms=180_000,
    )

    assert plans[0].segments != plans[1].segments or plans[0].target_duration_ms != plans[1].target_duration_ms


def test_missing_candidates_are_filled_to_reach_target_duration() -> None:
    sources = (_source("ep1", 0, 180_000), _source("ep2", 1, 180_000))

    plans = build_story_plans(
        _analysis((), 360_000),
        sources,
        target_count=2,
        min_duration_ms=120_000,
        max_duration_ms=120_000,
    )

    assert len(plans) == 2
    for plan in plans:
        assert plan.duration_ms >= 108_000
        assert plan.segments


def test_media_shorter_than_minimum_is_rejected() -> None:
    with pytest.raises(ValueError):
        build_story_plans(
            _analysis((), 60_000),
            (_source("ep1", 0, 60_000),),
            target_count=1,
            min_duration_ms=120_000,
            max_duration_ms=180_000,
        )


def test_duration_window_below_one_minute_is_rejected() -> None:
    with pytest.raises(ValueError):
        build_story_plans(
            _analysis((), 600_000),
            (_source("ep1", 0, 600_000),),
            target_count=1,
            min_duration_ms=30_000,
            max_duration_ms=60_000,
        )
