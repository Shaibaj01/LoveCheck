"""Aggregate VastDB row snapshots into dashboard statistics."""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


def _is_segment_row(row: dict) -> bool:
    kind = str(row.get("row_kind") or "").strip().lower()
    return kind in ("", "segment")


def _split_object_classes(value: Any) -> List[str]:
    text = str(value or "").strip()
    if not text:
        return []
    parts: List[str] = []
    for part in text.replace("|", ",").replace(";", ",").split(","):
        label = part.strip().lower()
        if label:
            parts.append(label)
    return parts


def _parse_upload_day(value: Any) -> Optional[str]:
    if value is None:
        return None
    if hasattr(value, "to_pydatetime"):
        value = value.to_pydatetime()
    if isinstance(value, datetime):
        dt = value
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.date().isoformat()
    text = str(value).strip()
    if not text:
        return None
    try:
        normalized = text.replace("Z", "+00:00")
        return datetime.fromisoformat(normalized).date().isoformat()
    except ValueError:
        return text[:10] if len(text) >= 10 else None


def _metadata_label(value: Any) -> str:
    text = str(value or "").strip()
    return text if text else "(empty)"


def build_dashboard_stats(rows: List[dict]) -> Dict[str, Any]:
    """Build dashboard payload from accessible VastDB rows."""
    segment_rows = [r for r in rows if _is_segment_row(r)]
    summary_rows = [r for r in rows if str(r.get("row_kind") or "").strip().lower() == "video_summary"]
    other_rows = len(rows) - len(segment_rows) - len(summary_rows)

    videos = {
        str(r.get("original_video") or r.get("source") or "").strip()
        for r in segment_rows
        if str(r.get("original_video") or r.get("source") or "").strip()
    }

    slot_counter: Counter[tuple[str, int]] = Counter()
    for row in segment_rows:
        video = str(row.get("original_video") or row.get("source") or "").strip()
        sn = int(row.get("segment_number") or 0)
        if video and sn > 0:
            slot_counter[(video, sn)] += 1

    duplicate_slots = sum(1 for count in slot_counter.values() if count > 1)
    duplicate_rows = sum(count - 1 for count in slot_counter.values() if count > 1)

    object_counter: Counter[str] = Counter()
    for row in segment_rows:
        for label in _split_object_classes(row.get("object_classes")):
            object_counter[label] += 1

    metadata_fields = ("camera_id", "capture_type", "location")
    metadata_breakdown: Dict[str, List[Dict[str, Any]]] = {}
    for field in metadata_fields:
        counter: Counter[str] = Counter()
        for row in segment_rows:
            counter[_metadata_label(row.get(field))] += 1
        metadata_breakdown[field] = [
            {"label": label, "count": count}
            for label, count in counter.most_common(20)
        ]

    uploads_by_day: Counter[str] = Counter()
    for row in segment_rows:
        day = _parse_upload_day(row.get("upload_timestamp"))
        if day:
            uploads_by_day[day] += 1

    public_segments = sum(1 for r in segment_rows if bool(r.get("is_public")))
    structured_ok = sum(1 for r in segment_rows if bool(r.get("structured_parse_ok")))
    perception_ok = sum(1 for r in segment_rows if bool(r.get("perception_ok")))
    with_objects = sum(1 for r in segment_rows if _split_object_classes(r.get("object_classes")))

    video_stats: Dict[str, dict] = {}
    for row in segment_rows:
        video = str(row.get("original_video") or row.get("source") or "").strip()
        if not video:
            continue
        entry = video_stats.setdefault(
            video,
            {
                "original_video": video,
                "filename": str(row.get("filename") or video.rsplit("/", 1)[-1]),
                "segment_rows": 0,
                "unique_segments": set(),
                "upload_timestamp": row.get("upload_timestamp"),
                "camera_id": _metadata_label(row.get("camera_id")),
                "capture_type": _metadata_label(row.get("capture_type")),
                "location": _metadata_label(row.get("location")),
                "is_public": bool(row.get("is_public")),
                "total_segments": int(row.get("total_segments") or 0),
            },
        )
        entry["segment_rows"] += 1
        sn = int(row.get("segment_number") or 0)
        if sn > 0:
            entry["unique_segments"].add(sn)
        ts = row.get("upload_timestamp")
        if ts is not None and (entry["upload_timestamp"] is None or str(ts) > str(entry["upload_timestamp"])):
            entry["upload_timestamp"] = ts

    recent_videos: List[Dict[str, Any]] = []
    for video, entry in video_stats.items():
        unique_count = len(entry["unique_segments"]) or entry["segment_rows"]
        expected = int(entry["total_segments"] or 0)
        recent_videos.append(
            {
                "original_video": video,
                "filename": entry["filename"],
                "segment_rows": entry["segment_rows"],
                "unique_segments": unique_count,
                "expected_segments": expected,
                "duplicate_rows": max(0, entry["segment_rows"] - unique_count),
                "upload_timestamp": _format_timestamp(entry["upload_timestamp"]),
                "camera_id": entry["camera_id"],
                "capture_type": entry["capture_type"],
                "location": entry["location"],
                "is_public": entry["is_public"],
            }
        )

    recent_videos.sort(key=lambda item: item.get("upload_timestamp") or "", reverse=True)

    segment_total = len(segment_rows)
    quality = {
        "structured_parse_ok": structured_ok,
        "structured_parse_ok_pct": round((structured_ok / segment_total) * 100, 1) if segment_total else 0.0,
        "perception_ok": perception_ok,
        "perception_ok_pct": round((perception_ok / segment_total) * 100, 1) if segment_total else 0.0,
        "with_object_classes": with_objects,
        "with_object_classes_pct": round((with_objects / segment_total) * 100, 1) if segment_total else 0.0,
    }

    return {
        "overview": {
            "total_rows": len(rows),
            "segment_rows": segment_total,
            "video_summary_rows": len(summary_rows),
            "other_rows": other_rows,
            "unique_videos": len(videos),
            "duplicate_segment_slots": duplicate_slots,
            "duplicate_segment_rows": duplicate_rows,
            "public_segment_rows": public_segments,
            "private_segment_rows": segment_total - public_segments,
        },
        "quality": quality,
        "objects": [
            {"label": label, "segment_count": count}
            for label, count in object_counter.most_common(25)
        ],
        "metadata": metadata_breakdown,
        "uploads_by_day": [
            {"date": day, "segment_rows": count}
            for day, count in sorted(uploads_by_day.items())
        ],
        "recent_videos": recent_videos[:15],
    }


def empty_dashboard_stats() -> Dict[str, Any]:
    """Zeroed dashboard payload when the table is empty or unavailable."""
    return {
        "overview": {
            "total_rows": 0,
            "segment_rows": 0,
            "video_summary_rows": 0,
            "other_rows": 0,
            "unique_videos": 0,
            "duplicate_segment_slots": 0,
            "duplicate_segment_rows": 0,
            "public_segment_rows": 0,
            "private_segment_rows": 0,
        },
        "quality": {
            "structured_parse_ok": 0,
            "structured_parse_ok_pct": 0.0,
            "perception_ok": 0,
            "perception_ok_pct": 0.0,
            "with_object_classes": 0,
            "with_object_classes_pct": 0.0,
        },
        "objects": [],
        "metadata": {
            "camera_id": [],
            "capture_type": [],
            "location": [],
        },
        "uploads_by_day": [],
        "recent_videos": [],
    }


def _format_timestamp(value: Any) -> Optional[str]:
    if value is None:
        return None
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)
