from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Sequence

from blueframe.asr.models import AsrLine
from blueframe.drama.models import StoryAnalysis
from blueframe.highlights.models import HighlightClipSpec
from blueframe.projects.models import ProjectSource


@dataclass(frozen=True)
class _Window:
    source: ProjectSource
    offset_ms: int
    duration_ms: int


def build_highlight_clips(
    analysis: StoryAnalysis,
    sources: Sequence[ProjectSource],
    *,
    target_count: int,
    min_duration_ms: int,
    max_duration_ms: int,
    lines_by_source: Mapping[str, Sequence[AsrLine]] | None = None,
    snap_tolerance_ms: int = 1200,
    overlap_limit: float = 0.5,
    minimum_clip_ms: int = 3000,
) -> tuple[HighlightClipSpec, ...]:
    if target_count < 1:
        raise ValueError("target_count must be positive")
    if min_duration_ms < minimum_clip_ms or max_duration_ms < min_duration_ms:
        raise ValueError("invalid clip duration window")
    windows = _windows(sources)
    if not windows:
        return ()
    lines_by_source = lines_by_source or {}

    accepted: list[HighlightClipSpec] = []
    for explosion in sorted(analysis.explosions, key=lambda item: (-item.score, item.start_ms)):
        window = _window_for(windows, (explosion.start_ms + explosion.end_ms) // 2)
        local_mid = _clamp(
            (explosion.start_ms + explosion.end_ms) // 2 - window.offset_ms,
            0,
            window.duration_ms,
        )
        desired = _clamp(explosion.end_ms - explosion.start_ms, min_duration_ms, max_duration_ms)
        start = local_mid - desired // 2
        end = start + desired
        lines = lines_by_source.get(window.source.id, ())
        if lines:
            start, end = _snap(start, end, lines, snap_tolerance_ms)
        start, end = _fit(start, end, window.duration_ms, min_duration_ms, max_duration_ms, minimum_clip_ms)
        if start is None:
            continue
        candidate = HighlightClipSpec(
            title=explosion.title,
            reason=explosion.reason,
            score=explosion.score,
            source_id=window.source.id,
            start_ms=start,
            end_ms=end,
        )
        if any(_overlap_ratio(candidate, kept) > overlap_limit for kept in accepted):
            continue
        accepted.append(candidate)
        if len(accepted) >= target_count:
            break
    return tuple(accepted)


def _windows(sources: Sequence[ProjectSource]) -> tuple[_Window, ...]:
    windows: list[_Window] = []
    offset = 0
    for source in sorted(sources, key=lambda item: item.order_index):
        duration = int((source.media_info or {}).get("duration_ms") or 0)
        if duration <= 0:
            continue
        windows.append(_Window(source=source, offset_ms=offset, duration_ms=duration))
        offset += duration
    return tuple(windows)


def _window_for(windows: Sequence[_Window], global_ms: int) -> _Window:
    for window in windows:
        if window.offset_ms <= global_ms < window.offset_ms + window.duration_ms:
            return window
    return windows[0] if global_ms < windows[0].offset_ms else windows[-1]


def _snap(
    start: int,
    end: int,
    lines: Sequence[AsrLine],
    tolerance_ms: int,
) -> tuple[int, int]:
    snapped_start = start
    for line in lines:
        if line.start_ms <= start and start - line.start_ms <= tolerance_ms:
            snapped_start = min(snapped_start, line.start_ms)
    snapped_end = end
    for line in lines:
        if line.end_ms >= end and line.end_ms - end <= tolerance_ms:
            snapped_end = max(snapped_end, line.end_ms)
    return snapped_start, snapped_end


def _fit(
    start: int,
    end: int,
    duration_ms: int,
    min_duration_ms: int,
    max_duration_ms: int,
    minimum_clip_ms: int,
) -> tuple[int | None, int]:
    if duration_ms < minimum_clip_ms:
        return None, 0
    start = max(0, min(start, duration_ms - minimum_clip_ms))
    end = min(end, duration_ms)
    if end - start > max_duration_ms:
        end = start + max_duration_ms
    if end - start < min_duration_ms:
        end = min(duration_ms, start + min_duration_ms)
        start = max(0, end - min_duration_ms)
    if end - start < minimum_clip_ms:
        return None, 0
    return start, end


def _overlap_ratio(first: HighlightClipSpec, second: HighlightClipSpec) -> float:
    if first.source_id != second.source_id:
        return 0.0
    overlap = min(first.end_ms, second.end_ms) - max(first.start_ms, second.start_ms)
    if overlap <= 0:
        return 0.0
    shortest = min(first.duration_ms, second.duration_ms)
    return 0.0 if shortest <= 0 else overlap / shortest


def _clamp(value: int, lower: int, upper: int) -> int:
    return max(lower, min(value, upper))
