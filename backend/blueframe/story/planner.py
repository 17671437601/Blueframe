from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Mapping, Sequence

from blueframe.asr.models import AsrLine
from blueframe.drama.models import StoryAnalysis
from blueframe.projects.models import ProjectSource
from blueframe.story.models import StoryPlanSpec, StorySegmentSpec

MIN_SEGMENT_MS = 4_000
MAX_SEGMENT_MS = 45_000
SNAP_TOLERANCE_MS = 1_200
MERGE_GAP_MS = 1_500
MIN_OUTPUT_MS = 60_000
SIMILARITY_LIMIT = 0.82


@dataclass(frozen=True)
class _Window:
    source: ProjectSource
    offset_ms: int
    duration_ms: int


@dataclass
class _Candidate:
    window_index: int
    start_ms: int
    end_ms: int
    score: int
    title: str

    @property
    def duration_ms(self) -> int:
        return self.end_ms - self.start_ms


def build_story_plans(
    analysis: StoryAnalysis,
    sources: Sequence[ProjectSource],
    *,
    target_count: int,
    min_duration_ms: int,
    max_duration_ms: int,
    lines_by_source: Mapping[str, Sequence[AsrLine]] | None = None,
    seed: int = 0,
    duration_tolerance: float = 0.08,
) -> tuple[StoryPlanSpec, ...]:
    if target_count < 1:
        raise ValueError("target_count must be positive")
    if min_duration_ms < MIN_OUTPUT_MS:
        raise ValueError("story output must be at least one minute")
    if max_duration_ms < min_duration_ms:
        raise ValueError("invalid story duration window")
    windows = _windows(sources)
    if not windows:
        return ()
    total_duration = sum(window.duration_ms for window in windows)
    if total_duration < min_duration_ms:
        raise ValueError("media is shorter than the requested minimum duration")

    candidates = _candidates(analysis, windows)
    lines_by_source = lines_by_source or {}
    plans: list[StoryPlanSpec] = []
    for index in range(target_count):
        plan = _build_one(
            windows,
            candidates,
            lines_by_source,
            target_count=target_count,
            min_duration_ms=min_duration_ms,
            max_duration_ms=max_duration_ms,
            total_duration=total_duration,
            tolerance=duration_tolerance,
            seed=seed,
            variant=index,
            title_index=index,
        )
        attempts = 0
        while attempts < 3 and plans and _similarity(plans[-1], plan) > SIMILARITY_LIMIT:
            attempts += 1
            plan = _build_one(
                windows,
                candidates,
                lines_by_source,
                target_count=target_count,
                min_duration_ms=min_duration_ms,
                max_duration_ms=max_duration_ms,
                total_duration=total_duration,
                tolerance=duration_tolerance,
                seed=seed,
                variant=index + attempts * 31,
                title_index=index,
            )
        plans.append(plan)
    return tuple(plans)


def _build_one(
    windows: Sequence[_Window],
    candidates: Sequence[_Candidate],
    lines_by_source: Mapping[str, Sequence[AsrLine]],
    *,
    target_count: int,
    min_duration_ms: int,
    max_duration_ms: int,
    total_duration: int,
    tolerance: float,
    seed: int,
    variant: int,
    title_index: int,
) -> StoryPlanSpec:
    rng = random.Random(seed * 100_003 + variant * 7_919 + 17)
    target = min(rng.randint(min_duration_ms, max_duration_ms), total_duration)
    counts = [0] * len(windows)
    for candidate in candidates:
        counts[candidate.window_index] += 1
    weights = [
        window.duration_ms * (1 + 0.5 * min(counts[index], 8))
        for index, window in enumerate(windows)
    ]
    weight_total = sum(weights) or 1
    quotas = [target * weight / weight_total for weight in weights]

    picked: list[_Candidate] = []
    for index, window in enumerate(windows):
        pool = [item for item in candidates if item.window_index == index]
        picked.extend(_pick(pool, window, index, quotas[index], rng))
    if not picked:
        picked = _fallback(windows, target)
    picked.sort(key=lambda item: (item.window_index, item.start_ms))
    picked = _merge(picked)
    picked = _balance(picked, windows, target, tolerance)
    segments = _segments(picked, windows, lines_by_source)
    return StoryPlanSpec(
        title=f"主线成片 {title_index + 1}",
        target_duration_ms=target,
        segments=segments,
    )


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


def _candidates(analysis: StoryAnalysis, windows: Sequence[_Window]) -> list[_Candidate]:
    raw: list[tuple[int, int, int, str]] = []
    for explosion in analysis.explosions:
        raw.append((explosion.start_ms, explosion.end_ms, explosion.score, explosion.title))
    for conflict in analysis.conflicts:
        raw.append((conflict.start_ms, conflict.end_ms, 60, conflict.summary[:60]))
    for candidate in analysis.edit_candidates:
        for start_ms, end_ms in candidate.segments:
            raw.append((start_ms, end_ms, 70, candidate.title))

    accepted: list[_Candidate] = []
    for start_ms, end_ms, score, title in sorted(raw, key=lambda item: (-item[2], item[0])):
        window_index = _window_index(windows, (start_ms + end_ms) // 2)
        if window_index is None:
            continue
        window = windows[window_index]
        local_start = max(0, start_ms - window.offset_ms)
        local_end = min(window.duration_ms, end_ms - window.offset_ms)
        if local_end - local_start < 1_500:
            continue
        item = _Candidate(
            window_index=window_index,
            start_ms=local_start,
            end_ms=local_end,
            score=score,
            title=title or "剧情片段",
        )
        if any(
            kept.window_index == item.window_index and _overlap_ratio(item, kept) > 0.7
            for kept in accepted
        ):
            continue
        accepted.append(item)
    return accepted


def _window_index(windows: Sequence[_Window], global_ms: int) -> int | None:
    for index, window in enumerate(windows):
        if window.offset_ms <= global_ms < window.offset_ms + window.duration_ms:
            return index
    if not windows:
        return None
    return 0 if global_ms < windows[0].offset_ms else len(windows) - 1


def _pick(
    pool: Sequence[_Candidate],
    window: _Window,
    window_index: int,
    quota: float,
    rng: random.Random,
) -> list[_Candidate]:
    if quota < MIN_SEGMENT_MS:
        return []
    scored = sorted(
        pool,
        key=lambda item: (-(item.score + rng.uniform(-12, 12)), item.start_ms),
    )
    accepted: list[_Candidate] = []
    used = 0
    for candidate in scored:
        if used >= quota * 0.92:
            break
        normalized = _normalize(candidate, window)
        if normalized is None:
            continue
        if any(_overlap_ratio(normalized, kept) > 0 for kept in accepted):
            continue
        if accepted and used + normalized.duration_ms > quota * 1.3:
            continue
        accepted.append(normalized)
        used += normalized.duration_ms
    if used < quota * 0.8:
        _fill(accepted, window, quota - used, window_index=window_index)
    return accepted


def _normalize(candidate: _Candidate, window: _Window) -> _Candidate | None:
    start = max(0, min(candidate.start_ms, window.duration_ms - 500))
    end = min(window.duration_ms, max(candidate.end_ms, start + 500))
    if end - start < MIN_SEGMENT_MS:
        center = (start + end) // 2
        start = max(0, center - MIN_SEGMENT_MS // 2)
        end = min(window.duration_ms, start + MIN_SEGMENT_MS)
        start = max(0, end - MIN_SEGMENT_MS)
    if end - start > MAX_SEGMENT_MS:
        end = start + MAX_SEGMENT_MS
    if end - start < 1_500:
        return None
    return _Candidate(
        window_index=candidate.window_index,
        start_ms=start,
        end_ms=end,
        score=candidate.score,
        title=candidate.title,
    )


def _fill(accepted: list[_Candidate], window: _Window, remaining: float, *, window_index: int) -> None:
    if remaining < MIN_SEGMENT_MS:
        return
    position = 0
    guard = 0
    while remaining >= MIN_SEGMENT_MS and position < window.duration_ms and guard < 200:
        guard += 1
        length = int(min(remaining, MAX_SEGMENT_MS, 20_000, window.duration_ms - position))
        if length < MIN_SEGMENT_MS:
            break
        candidate = _Candidate(
            window_index=window_index,
            start_ms=position,
            end_ms=position + length,
            score=30,
            title="剧情铺垫",
        )
        if all(_overlap_ratio(candidate, kept) == 0 for kept in accepted):
            accepted.append(candidate)
            remaining -= length
            position += length
        else:
            position += 2_000


def _fallback(windows: Sequence[_Window], target: int) -> list[_Candidate]:
    picked: list[_Candidate] = []
    remaining = target
    for index, window in enumerate(windows):
        if remaining <= 0:
            break
        length = int(min(remaining, window.duration_ms, 20_000))
        if length < MIN_SEGMENT_MS:
            continue
        picked.append(_Candidate(index, 0, length, 20, "剧情片段"))
        remaining -= length
    return picked


def _merge(selected: list[_Candidate]) -> list[_Candidate]:
    merged: list[_Candidate] = []
    for item in selected:
        if (
            merged
            and merged[-1].window_index == item.window_index
            and item.start_ms - merged[-1].end_ms <= MERGE_GAP_MS
        ):
            merged[-1].end_ms = max(merged[-1].end_ms, item.end_ms)
            merged[-1].score = max(merged[-1].score, item.score)
            continue
        merged.append(item)
    return merged


def _balance(
    selected: list[_Candidate],
    windows: Sequence[_Window],
    target: int,
    tolerance: float,
) -> list[_Candidate]:
    low = int(target * (1 - tolerance))
    high = int(target * (1 + tolerance))
    total = sum(item.duration_ms for item in selected)
    while total > high and len(selected) > 1:
        victim = min(range(len(selected)), key=lambda index: selected[index].score)
        total -= selected.pop(victim).duration_ms
    guard = 0
    while total < low and guard < 128:
        guard += 1
        if not _grow(selected, windows, low - total):
            break
        total = sum(item.duration_ms for item in selected)
    return selected


def _grow(selected: list[_Candidate], windows: Sequence[_Window], need: int) -> bool:
    for index, item in enumerate(selected):
        window = windows[item.window_index]
        next_start = window.duration_ms
        for later in selected[index + 1 :]:
            if later.window_index == item.window_index:
                next_start = later.start_ms
                break
        room = next_start - item.end_ms
        if room >= 1_000:
            item.end_ms += int(min(room, max(need, 0), 20_000))
            return True
        previous_end = 0
        for earlier in reversed(selected[:index]):
            if earlier.window_index == item.window_index:
                previous_end = earlier.end_ms
                break
        room_left = item.start_ms - previous_end
        if room_left >= 1_000:
            item.start_ms -= int(min(room_left, max(need, 0), 20_000))
            return True
    return False


def _segments(
    selected: Sequence[_Candidate],
    windows: Sequence[_Window],
    lines_by_source: Mapping[str, Sequence[AsrLine]],
) -> tuple[StorySegmentSpec, ...]:
    specs: list[StorySegmentSpec] = []
    previous_end: dict[str, int] = {}
    for item in selected:
        window = windows[item.window_index]
        start, end = item.start_ms, item.end_ms
        lines = lines_by_source.get(window.source.id, ())
        if lines:
            start, end = _snap(start, end, lines)
        start = max(0, min(start, window.duration_ms - 500))
        end = max(start + 500, min(end, window.duration_ms))
        floor = previous_end.get(window.source.id, 0)
        if start < floor:
            start = floor
        if end - start < 500:
            continue
        specs.append(
            StorySegmentSpec(source_id=window.source.id, start_ms=start, end_ms=end)
        )
        previous_end[window.source.id] = end
    if not specs:
        raise ValueError("story planner produced no usable segments")
    return tuple(specs)


def _snap(start: int, end: int, lines: Sequence[AsrLine]) -> tuple[int, int]:
    snapped_start = start
    for line in lines:
        if line.start_ms <= start and start - line.start_ms <= SNAP_TOLERANCE_MS:
            snapped_start = min(snapped_start, line.start_ms)
    snapped_end = end
    for line in lines:
        if line.end_ms >= end and line.end_ms - end <= SNAP_TOLERANCE_MS:
            snapped_end = max(snapped_end, line.end_ms)
    return snapped_start, snapped_end


def _overlap_ratio(first: _Candidate, second: _Candidate) -> float:
    if first.window_index != second.window_index:
        return 0.0
    overlap = min(first.end_ms, second.end_ms) - max(first.start_ms, second.start_ms)
    if overlap <= 0:
        return 0.0
    shortest = min(first.duration_ms, second.duration_ms)
    return 0.0 if shortest <= 0 else overlap / shortest


def _similarity(first: StoryPlanSpec, second: StoryPlanSpec) -> float:
    total_first = sum(segment.duration_ms for segment in first.segments)
    total_second = sum(segment.duration_ms for segment in second.segments)
    shortest = min(total_first, total_second)
    if shortest <= 0:
        return 0.0
    overlap = 0
    for left in first.segments:
        for right in second.segments:
            if left.source_id != right.source_id:
                continue
            shared = min(left.end_ms, right.end_ms) - max(left.start_ms, right.start_ms)
            if shared > 0:
                overlap += shared
    return min(1.0, overlap / shortest)
