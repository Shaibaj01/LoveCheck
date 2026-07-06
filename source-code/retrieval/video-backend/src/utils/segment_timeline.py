"""Timeline helpers for deduplicating segment rows."""
from typing import Any, Callable, List, TypeVar

T = TypeVar("T")


def _segment_dict_rank(seg: dict) -> tuple:
    """Prefer newest ingest, then richer caption, for duplicate segment_number rows."""
    ts = seg.get("upload_timestamp")
    if ts is not None and hasattr(ts, "isoformat"):
        ts_key = ts.isoformat()
    else:
        ts_key = str(ts or "")
    cap = len(str(seg.get("dense_caption") or ""))
    return (ts_key, cap)


def dedupe_segment_dicts(segments: List[dict]) -> List[dict]:
    """One row per segment_number (re-ingest can leave multiple VastDB rows per slot)."""
    best_by_number: dict[int, dict] = {}
    for seg in segments:
        sn = int(seg.get("segment_number") or 0)
        if sn <= 0:
            continue
        prev = best_by_number.get(sn)
        if prev is None or _segment_dict_rank(seg) > _segment_dict_rank(prev):
            best_by_number[sn] = seg
    return [best_by_number[k] for k in sorted(best_by_number)]


def expected_total_segments(segments: List[dict]) -> int:
    """Largest total_segments value declared on rows for one parent chunk."""
    expected = 0
    for seg in segments:
        try:
            total = int(seg.get("total_segments") or 0)
        except (TypeError, ValueError):
            total = 0
        if total > expected:
            expected = total
    return expected


def is_chunk_fully_indexed(segments: List[dict]) -> bool:
    """True when indexed segment rows cover every slot 1..total_segments."""
    if not segments:
        return False
    expected = expected_total_segments(segments)
    if expected <= 0:
        return False
    deduped = dedupe_segment_dicts(segments)
    if len(deduped) != expected:
        return False
    numbers = {int(seg.get("segment_number") or 0) for seg in deduped}
    return numbers == set(range(1, expected + 1))


def dedupe_by_segment_number(
    items: List[T],
    segment_number: Callable[[T], int],
    rank_key: Callable[[T], Any],
) -> List[T]:
    """Keep the highest-ranked item per segment_number."""
    best: dict[int, T] = {}
    for item in items:
        sn = segment_number(item)
        if sn <= 0:
            continue
        prev = best.get(sn)
        if prev is None or rank_key(item) > rank_key(prev):
            best[sn] = item
    return [best[k] for k in sorted(best)]
