"""Deduplicate similar key events and search prompts."""
import re
from typing import Any, Dict, List, Set

_STOP = frozenset({
    "the", "and", "for", "with", "near", "along", "from", "that", "this",
    "into", "over", "under", "across", "through", "street", "sidewalk",
    "road", "city", "urban", "video", "clip", "scene",
})


def _tokens(text: str) -> Set[str]:
    return {
        w for w in re.findall(r"[a-z0-9]+", (text or "").lower())
        if len(w) > 2 and w not in _STOP
    }


def similar_text(a: str, b: str, threshold: float = 0.52) -> bool:
    ta, tb = _tokens(a), _tokens(b)
    if not ta or not tb:
        return (a or "").strip().lower() == (b or "").strip().lower()
    overlap = len(ta & tb)
    union = len(ta | tb)
    return overlap / union >= threshold


def _event_key(ev: Dict[str, Any]) -> tuple:
    return (
        str(ev.get("original_video") or ""),
        round(float(ev.get("segment_start_sec") or 0), 0),
    )


def dedupe_key_events(events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Drop near-duplicate events (same video + time + similar wording)."""
    kept: List[Dict[str, Any]] = []
    for ev in events:
        q = str(ev.get("query_text") or "").strip()
        if not q:
            continue
        duplicate = False
        for existing in kept:
            if _event_key(existing) != _event_key(ev):
                if str(existing.get("original_video")) != str(ev.get("original_video")):
                    continue
                start_a = float(existing.get("segment_start_sec") or 0)
                start_b = float(ev.get("segment_start_sec") or 0)
                if abs(start_a - start_b) > 12:
                    continue
            label_a = str(existing.get("label") or existing.get("query_text") or "")
            label_b = str(ev.get("label") or q)
            if similar_text(q, str(existing.get("query_text") or "")) or similar_text(
                label_a, label_b
            ):
                duplicate = True
                break
        if not duplicate:
            kept.append(ev)
    return kept


def dedupe_prompts(prompts: List[str]) -> List[str]:
    kept: List[str] = []
    for p in prompts:
        q = p.strip()
        if not q:
            continue
        if any(similar_text(q, k) for k in kept):
            continue
        kept.append(q)
    return kept
