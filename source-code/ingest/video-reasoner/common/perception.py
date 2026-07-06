"""
Perception lite: fast object listing on segment video before main VLM reasoning.
Uses Cosmos-Reason2 with a short JSON-only prompt.
"""
import json
import logging
import re
from typing import Any, Dict, List

from .prompts import PERCEPTION_OBJECT_PROMPT
from .structured_output import extract_json_object, _strip_json_fences

logger = logging.getLogger(__name__)

EMPTY_PERCEPTION = {
    "perception_json": "",
    "object_classes": "",
    "object_counts": "{}",
    "max_detection_conf": 0.0,
    "perception_ok": False,
    "perception_summary": "",
}

SUMMARY_FIELD_RE = re.compile(
    r'"(?:summary|scene_summary)"\s*:\s*"((?:\\.|[^"\\])*)"',
    re.IGNORECASE,
)
DETECTION_LINE_RE = re.compile(
    r'(\d+)\s+(people|persons|pedestrians|men|women|children|gorillas?|ambulances?|'
    r'forklifts?|trucks?|cranes?|cameras?|billboards?|statues?|signboards?)',
    re.IGNORECASE,
)
NAMED_ENTITY_RE = re.compile(
    r'\b(minnie mouse|cherry picker|digital billboard|gorilla costume|minnie mouse costume)\b',
    re.IGNORECASE,
)


def _parse_perception_response(raw: str) -> Dict[str, Any]:
    text = (raw or "").strip()
    if not text:
        return {}
    try:
        return extract_json_object(text)
    except (ValueError, json.JSONDecodeError):
        logger.warning("[PERCEPTION] Failed strict JSON parse; trying prose recovery")

    cleaned = _strip_json_fences(text)
    summary_match = SUMMARY_FIELD_RE.search(cleaned)
    summary = ""
    if summary_match:
        try:
            summary = str(json.loads(f'"{summary_match.group(1)}"')).strip()
        except json.JSONDecodeError:
            summary = summary_match.group(1).replace('\\"', '"').strip()

    detections: List[Dict[str, Any]] = []
    lower = cleaned.lower()
    for match in DETECTION_LINE_RE.finditer(lower):
        count = int(match.group(1))
        label = match.group(2).lower().rstrip("s")
        if label in ("people", "person", "pedestrian", "men", "women", "child"):
            label = "person"
        if label == "billboard":
            label = "signboard"
        detections.append({"class": label, "count": count, "confidence": 0.75})

    for match in NAMED_ENTITY_RE.finditer(lower):
        label = match.group(1).lower()
        if "gorilla" in label:
            label = "gorilla"
        elif "minnie mouse" in label:
            label = "minnie mouse"
        elif "cherry picker" in label:
            label = "cherry picker"
        elif "billboard" in label:
            label = "signboard"
        detections.append({"class": label, "count": 1, "confidence": 0.7})

    if detections or summary:
        return {"detections": detections, "summary": summary}
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
        "max_conf": max(confidences) if confidences else (0.75 if classes else 0.0),
    }


def run_perception_lite(reasoning_client, video_content: bytes, settings) -> Dict[str, Any]:
    """Run a short VLM pass to list visible objects before main reasoning."""
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


def perception_from_detector(data: Dict[str, Any]) -> Dict[str, Any]:
    """Build perception dict from upstream YOLO detector payload."""
    object_counts_raw = data.get("object_counts") or "{}"
    summary = ""
    try:
        parsed = json.loads(object_counts_raw) if isinstance(object_counts_raw, str) else object_counts_raw
        if isinstance(parsed, dict) and parsed:
            parts = [f"{k} x{v}" if int(v) > 1 else k for k, v in sorted(parsed.items())]
            summary = "Detected: " + ", ".join(parts)
    except (json.JSONDecodeError, TypeError, ValueError):
        pass

    return {
        "perception_json": data.get("perception_json", ""),
        "object_classes": data.get("object_classes", ""),
        "object_counts": object_counts_raw if isinstance(object_counts_raw, str) else json.dumps(object_counts_raw),
        "max_detection_conf": float(data.get("max_detection_conf") or 0.0),
        "perception_ok": bool(data.get("perception_ok")),
        "perception_summary": summary,
        "perception_source": data.get("perception_source", "yolo11_coco"),
        "detection_sidecar_uri": data.get("detection_sidecar_uri", ""),
        "detection_frame_count": int(data.get("detection_frame_count") or 0),
        "detection_count": int(data.get("detection_count") or 0),
    }


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
