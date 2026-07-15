"""Estimate concurrent object counts from YOLO frame detections."""
from __future__ import annotations

import math
from typing import Any, Dict, List, Optional


def _det_label(det: Dict[str, Any]) -> str:
    label = (
        det.get("class")
        or det.get("label")
        or det.get("name")
        or det.get("type")
        or ""
    )
    return str(label).strip().lower()


def estimate_unique_object_counts(
    frames: Optional[List[Any]],
    *,
    raw_counts: Optional[Dict[str, Any]] = None,
    frame_count: int = 0,
) -> Dict[str, int]:
    """
    Estimate concurrent objects per class for a clip.

    Prefer max boxes of each class in any single frame (needs frame dets).
    Fallback without frames: ceil(raw_sum / frame_count) — not unique IDs,
    but avoids summing every frame (e.g. person 1786 → ~6).
    True unique IDs require a tracker (ByteTrack etc.) upstream.
    """
    max_by_class: Dict[str, int] = {}
    if isinstance(frames, list) and frames:
        for frame in frames:
            if not isinstance(frame, dict):
                continue
            per_frame: Dict[str, int] = {}
            for det in frame.get("detections") or []:
                if not isinstance(det, dict):
                    continue
                label = _det_label(det)
                if not label:
                    continue
                per_frame[label] = per_frame.get(label, 0) + 1
            for label, n in per_frame.items():
                if n > max_by_class.get(label, 0):
                    max_by_class[label] = n
        if max_by_class:
            return max_by_class

    if not raw_counts or frame_count <= 0:
        out: Dict[str, int] = {}
        for key, val in (raw_counts or {}).items():
            label = str(key).strip().lower()
            if not label:
                continue
            try:
                out[label] = max(1, int(val))
            except (TypeError, ValueError):
                continue
        return out

    out = {}
    for key, val in raw_counts.items():
        label = str(key).strip().lower()
        if not label:
            continue
        try:
            total = int(val)
        except (TypeError, ValueError):
            continue
        if total <= 0:
            continue
        out[label] = max(1, int(math.ceil(total / float(frame_count))))
    return out
