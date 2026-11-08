from __future__ import annotations

from blueframe.editing.models import EditSegment


def normalize_segments(
    segments: tuple[EditSegment, ...],
    *,
    target_duration_ms: int,
    protected_head_ms: int = 0,
    protected_tail_ms: int = 0,
    merge_gap_ms: int = 150,
    minimum_segment_ms: int = 500,
) -> tuple[EditSegment, ...]:
    clipped: list[EditSegment] = []
    for segment in segments:
        start = max(segment.source_start_ms, protected_head_ms)
        end = min(segment.source_end_ms, segment.source_duration_ms - protected_tail_ms)
        if end - start < minimum_segment_ms:
            continue
        candidate = segment.model_copy(
            update={"source_start_ms": start, "source_end_ms": end}
        )
        if (
            clipped
            and clipped[-1].source_id == candidate.source_id
            and 0 <= candidate.source_start_ms - clipped[-1].source_end_ms <= merge_gap_ms
        ):
            clipped[-1] = clipped[-1].model_copy(
                update={"source_end_ms": candidate.source_end_ms}
            )
        else:
            clipped.append(candidate)

    result: list[EditSegment] = []
    remaining = target_duration_ms
    for segment in clipped:
        if remaining < minimum_segment_ms:
            break
        if segment.duration_ms <= remaining:
            result.append(segment)
            remaining -= segment.duration_ms
            continue
        result.append(
            segment.model_copy(
                update={"source_end_ms": segment.source_start_ms + remaining}
            )
        )
        remaining = 0
        break
    if not result:
        raise ValueError("no valid edit segments remain after normalization")
    return tuple(result)


def plan_similarity(
    first: tuple[EditSegment, ...],
    second: tuple[EditSegment, ...],
    *,
    bucket_ms: int = 500,
) -> float:
    def coverage(segments: tuple[EditSegment, ...]) -> set[tuple[str, int]]:
        return {
            (segment.source_id, bucket)
            for segment in segments
            for bucket in range(
                segment.source_start_ms // bucket_ms,
                (segment.source_end_ms - 1) // bucket_ms + 1,
            )
        }

    left, right = coverage(first), coverage(second)
    union = left | right
    return 1.0 if not union else len(left & right) / len(union)
