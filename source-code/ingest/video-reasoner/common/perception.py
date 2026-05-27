"""
Perception lite: fast object listing on segment video before main VLM reasoning.
Uses Cosmos-Reason2 with a short JSON-only prompt.
"""
import json
import logging
import re
from typing import Any, Dict, List, Optional

from .prompts import PERCEPTION_OBJECT_PROMPT

logger = logging.getLogger(__name__)

EMPTY_PERCEPTION = {
    "perception_json": "",
    "object_classes": "",
    "object_counts": "{}",
    "max_detection_conf": 0.0,
    "perception_ok": False,
    "perception_summary": "",
}


def _parse_perception_response(raw: str) -> Dict[str, Any]:
    text = (raw or "").strip()
    if not text:
        return {}
    match = re.search(r"\{[\s\S]*\}", text)
    if match:
        text = match.group(0)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        logger.warning("[PERCEPTION] Failed to parse JSON from VLM response")
        return {}


def _aggregate_detections(parsed: Dict[str, Any]) -> Dict[str, Any]:
    detections = parsed.get("detections") or parsed.get("objects") or []
    if isinstance(detections, dict):
        detections = [{"class": k, "count": v} for k, v in detections.items()]

    counts: Dict[str, int] = {}
    confidences: List[float] = []
    classes: List[str] = []

    for item in detections:
        if not isinstance(item, dict):
            continue
        label = (
            item.get("class")
            or item.get("type")
            or item.get("label")
            or item.get("name")
            or ""
        )
        label = str(label).strip().lower()
        if not label:
            continue
        try:
            conf = float(item.get("confidence", item.get("conf", 0)) or 0)
        except (TypeError, ValueError):
            conf = 0.0
        if conf > 0:
            confidences.append(conf)
        count = item.get("count", 1)
        try:
            count = max(1, int(count))
        except (TypeError, ValueError):
            count = 1
        counts[label] = counts.get(label, 0) + count
        if label not in classes:
            classes.append(label)

    summary = parsed.get("summary") or parsed.get("scene_summary") or ""
    if not summary and counts:
        parts = [f"{c} x{n}" if n > 1 else c for c, n in sorted(counts.items())]
        summary = "Detected: " + ", ".join(parts)

    return {
        "counts": counts,
        "classes": classes,
        "summary": str(summary).strip(),
        "max_conf": max(confidences) if confidences else 0.0,
    }


def run_perception_lite(reasoning_client, video_content: bytes, settings) -> Dict[str, Any]:
    """Run a short VLM pass to list visible objects before main reasoning."""
    if not getattr(settings, "perception_enabled", False):
        return dict(EMPTY_PERCEPTION)

    try:
        raw = reasoning_client.get_cosmos_reasoning(
            video_content,
            PERCEPTION_OBJECT_PROMPT,
            max_tokens=getattr(settings, "perception_max_tokens", 512),
        )
        content = raw.get("reasoning_content", "")
        parsed = _parse_perception_response(content)
        agg = _aggregate_detections(parsed)

        perception_doc = {
            "detections": [
                {"class": cls, "count": cnt}
                for cls, cnt in sorted(agg["counts"].items())
            ],
            "summary": agg["summary"],
            "provider": "cosmos",
        }

        return {
            "perception_json": json.dumps(perception_doc, ensure_ascii=False),
            "object_classes": ",".join(agg["classes"]),
            "object_counts": json.dumps(agg["counts"], ensure_ascii=False),
            "max_detection_conf": float(agg["max_conf"]),
            "perception_ok": bool(agg["classes"]),
            "perception_summary": agg["summary"],
        }
    except Exception as exc:
        logger.warning(f"[PERCEPTION] Lite perception failed (non-fatal): {exc}")
        return dict(EMPTY_PERCEPTION)


def format_perception_context(perception: Dict[str, Any]) -> str:
    """Build text block injected into the main VLM prompt."""
    summary = (perception.get("perception_summary") or "").strip()
    if not summary:
        counts = perception.get("object_counts") or "{}"
        try:
            parsed = json.loads(counts)
            if parsed:
                parts = [f"{k} x{v}" if int(v) > 1 else k for k, v in sorted(parsed.items())]
                summary = "Detected: " + ", ".join(parts)
        except json.JSONDecodeError:
            pass
    if not summary:
        return ""
    return (
        "Verified object perception for this clip (use these counts; do not invent extras):\n"
        f"{summary}\n\n"
    )
