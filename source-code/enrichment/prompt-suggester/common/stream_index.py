"""Stream/chunk index fields from VastDB extra_metadata."""
from __future__ import annotations

import json
from typing import Any, Dict, Optional


def parse_extra_metadata(raw: Any) -> Dict[str, Any]:
    if raw is None:
        return {}
    if isinstance(raw, dict):
        return raw
    text = str(raw).strip()
    if not text or text == "{}":
        return {}
    try:
        data = json.loads(text)
        return data if isinstance(data, dict) else {}
    except json.JSONDecodeError:
        return {}


def stream_fields_from_row(row: dict) -> Dict[str, Any]:
    extra = parse_extra_metadata(row.get("extra_metadata"))
    out: Dict[str, Any] = {}
    for key in ("stream_id", "chunk_index", "chunk_start_sec", "stream_position_sec", "ingest_kind"):
        val = row.get(key)
        if val is None or val == "":
            val = extra.get(key)
        if val is not None and val != "":
            out[key] = val
    return out


def chunk_key(row: dict) -> str:
    """Group segments from the same stream chunk (30s parent file)."""
    ov = str(row.get("original_video") or "").strip()
    if ov:
        return ov
    return str(row.get("source") or "").strip()


def timeline_sec(row: dict) -> float:
    stream = stream_fields_from_row(row)
    pos = stream.get("stream_position_sec")
    if pos is not None:
        try:
            return float(pos)
        except (TypeError, ValueError):
            pass
    try:
        return float(row.get("segment_start_sec") or 0)
    except (TypeError, ValueError):
        return 0.0
