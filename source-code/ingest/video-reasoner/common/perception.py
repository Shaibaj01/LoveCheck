"""YOLO detector perception helpers for video reasoner."""
import json
from typing import Any, Dict

EMPTY_PERCEPTION = {
    "perception_json": "",
    "object_classes": "",
    "object_counts": "{}",
    "max_detection_conf": 0.0,
    "perception_ok": False,
    "perception_summary": "",
}


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
