"""Helpers for explore/browse chunk assembly from VastDB rows."""
from __future__ import annotations

from typing import Dict, List, Optional, Set

from src.utils.segment_timeline import dedupe_segment_dicts, is_chunk_fully_indexed

# Exact field set previously inlined in VastDBService.build_browse_chunk_from_rows.
BROWSE_SEGMENT_FIELDS = frozenset({
    "filename",
    "source",
    "reasoning_content",
    "segment_number",
    "total_segments",
    "segment_start_sec",
    "segment_end_sec",
    "original_video",
    "upload_timestamp",
    "tags",
    "camera_id",
    "capture_type",
    "location",
    "object_classes",
    "object_counts",
    "is_public",
    "duration",
})


def row_to_browse_segment(row: dict, original_video: Optional[str] = None) -> dict:
    """Normalize a VastDB row into the segment dict used by browse chunk builders."""
    ov = original_video or str(row.get("original_video") or "")
    counts = row.get("object_counts")
    return {
        "filename": str(row.get("filename") or ""),
        "source": str(row.get("source") or ""),
        "reasoning_content": str(row.get("reasoning_content") or ""),
        "segment_number": int(row.get("segment_number") or 0),
        "total_segments": int(row.get("total_segments") or 0),
        "segment_start_sec": float(row.get("segment_start_sec") or 0),
        "segment_end_sec": float(row.get("segment_end_sec") or 0),
        "original_video": ov,
        "upload_timestamp": row.get("upload_timestamp"),
        "tags": row.get("tags") or [],
        "camera_id": str(row.get("camera_id") or ""),
        "capture_type": str(row.get("capture_type") or ""),
        "location": str(row.get("location") or ""),
        "object_classes": str(row.get("object_classes") or ""),
        "object_counts": str(counts) if counts not in (None, "") else "",
        "is_public": bool(row.get("is_public", True)),
        "duration": float(row.get("duration") or 0),
    }


def prepare_browse_segments(
    rows: List[dict],
    original_video: str,
    *,
    require_complete: bool = True,
) -> Optional[List[dict]]:
    """Return deduped browse segments. Incomplete chunks are omitted unless requested."""
    if not rows:
        return None
    if require_complete and not is_chunk_fully_indexed(rows):
        return None
    segments = [row_to_browse_segment(row, original_video) for row in rows]
    segments.sort(key=lambda seg: seg["segment_number"])
    segments = dedupe_segment_dicts(segments)
    return segments or None


def fully_indexed_videos(rows_by_video: Dict[str, List[dict]]) -> Set[str]:
    return {ov for ov, rows in rows_by_video.items() if is_chunk_fully_indexed(rows)}


def incomplete_videos(rows_by_video: Dict[str, List[dict]]) -> Set[str]:
    """Parent videos that have indexed rows but are missing at least one segment slot."""
    return {
        ov
        for ov, rows in rows_by_video.items()
        if rows and not is_chunk_fully_indexed(rows)
    }
