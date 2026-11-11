from datetime import UTC, datetime
from pathlib import Path

import pytest

from blueframe.drama.models import ExplosionCandidate, StoryAnalysis
from blueframe.highlights.planner import build_highlight_clips
from blueframe.projects.models import ProjectSource


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


def test_clips_map_back_to_their_source_and_drop_overlaps() -> None:
    sources = (_source("ep1", 0, 60_000), _source("ep2", 1, 60_000))
    analysis = _analysis(
        (
            _explosion(10_000, 14_000, 95, "第一集冲突"),
            _explosion(30_000, 34_000, 90, "第一集反转"),
            _explosion(31_000, 35_000, 70, "第一集反转重复"),
            _explosion(70_000, 74_000, 85, "第二集对峙"),
            _explosion(100_000, 104_000, 80, "第二集揭晓"),
        ),
        120_000,
    )

    clips = build_highlight_clips(
        analysis, sources, target_count=10, min_duration_ms=8_000, max_duration_ms=20_000,
    )

    assert [clip.title for clip in clips] == ["第一集冲突", "第一集反转", "第二集对峙", "第二集揭晓"]
    assert [clip.source_id for clip in clips] == ["ep1", "ep1", "ep2", "ep2"]
    assert clips[0].start_ms == 8_000 and clips[0].end_ms == 16_000
    assert clips[2].start_ms == 8_000 and clips[2].end_ms == 16_000
    assert all(8_000 <= clip.duration_ms <= 20_000 for clip in clips)


def test_target_count_keeps_highest_scores() -> None:
    sources = (_source("ep1", 0, 120_000),)
    analysis = _analysis(
        tuple(
            _explosion(index * 20_000, index * 20_000 + 4_000, 60 + index, f"高光 {index}")
            for index in range(5)
        ),
        120_000,
    )

    clips = build_highlight_clips(
        analysis, sources, target_count=2, min_duration_ms=8_000, max_duration_ms=20_000,
    )

    assert [clip.title for clip in clips] == ["高光 4", "高光 3"]


def test_clip_is_clamped_inside_source_bounds() -> None:
    sources = (_source("ep1", 0, 60_000),)
    analysis = _analysis((_explosion(0, 1_000, 99, "开场爆点"),), 60_000)

    clips = build_highlight_clips(
        analysis, sources, target_count=5, min_duration_ms=8_000, max_duration_ms=20_000,
    )

    assert len(clips) == 1
    assert clips[0].start_ms == 0
    assert clips[0].end_ms == 8_000


def test_invalid_duration_window_is_rejected() -> None:
    with pytest.raises(ValueError):
        build_highlight_clips(
            _analysis((), 60_000), (_source("ep1", 0, 60_000),),
            target_count=3, min_duration_ms=2_000, max_duration_ms=20_000,
        )
