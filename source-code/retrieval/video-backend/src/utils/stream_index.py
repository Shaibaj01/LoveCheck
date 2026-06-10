"""Parse stream/chunk indexing fields stored in VastDB extra_metadata or row dicts."""
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
    """Merge top-level row keys with extra_metadata stream index fields."""
    extra = parse_extra_metadata(row.get("extra_metadata"))
    out: Dict[str, Any] = {}
    for key in ("stream_id", "chunk_index", "chunk_start_sec", "stream_position_sec", "ingest_kind"):
        val = row.get(key)
        if val is None or val == "":
            val = extra.get(key)
        if val is not None and val != "":
            out[key] = val
    return out


def row_source_key(row: dict) -> str:
    """Stable identity for an indexed segment clip."""
    src = str(row.get("source") or "").strip()
    if src:
        return src
    ov = str(row.get("original_video") or "").strip()
    sn = int(row.get("segment_number") or 0)
    return f"{ov}#{sn}"


def format_stream_time(sec: Optional[float]) -> str:
    if sec is None:
        return "?"
    try:
        total = max(0, int(float(sec)))
    except (TypeError, ValueError):
        return "?"
    m, s = divmod(total, 60)
    h, m = divmod(m, 60)
    if h:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"
