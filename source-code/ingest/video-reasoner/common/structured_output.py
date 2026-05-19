"""
Parse VLM responses into structured JSON, dense captions for embedding, and UI narrative text.
"""
import json
import logging
import re
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

STRUCTURED_OUTPUT_INSTRUCTION = """
Respond with a single JSON object only. No markdown code fences, no text before or after the JSON.

Required schema:
{
  "scene_summary": "one factual sentence describing the clip",
  "objects": [{"type": "string", "count": 0, "notes": "optional details"}],
  "actions": ["observed actions as short strings"],
  "events": [{"type": "string", "description": "string", "severity": "low|medium|high|unknown"}],
  "hazards": ["safety or risk observations, empty array if none"],
  "attributes": {"setting": "optional key-value context"}
}

Rules:
- Describe only what is visible in this clip; do not guess or invent details.
- Use empty arrays when a category does not apply.
- Be specific about people, equipment, PPE, vehicles, and interactions when visible.
"""

DENSE_CAPTION_MAX_CHARS = 600


def wrap_prompt_with_structured_output(base_prompt: str) -> str:
    """Append JSON output instructions to scenario or custom prompts."""
    base = base_prompt.strip()
    if "Respond with a single JSON object only" in base:
        return base
    return f"{base}\n\n{STRUCTURED_OUTPUT_INSTRUCTION}"


def extract_json_object(text: str) -> Dict[str, Any]:
    """Extract and parse the first JSON object from model output."""
    if not text or not text.strip():
        raise ValueError("Empty VLM response")

    cleaned = text.strip()
    fence_match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", cleaned, re.IGNORECASE)
    if fence_match:
        cleaned = fence_match.group(1).strip()

    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("No JSON object found in VLM response")

    payload = cleaned[start : end + 1]
    data = json.loads(payload)
    if not isinstance(data, dict):
        raise ValueError("VLM JSON root must be an object")
    return data


def _normalize_list_field(data: Dict[str, Any], key: str) -> List[Any]:
    value = data.get(key, [])
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return []


def _coerce_structured(data: Dict[str, Any]) -> Dict[str, Any]:
    """Ensure expected keys exist with safe types."""
    objects = _normalize_list_field(data, "objects")
    normalized_objects = []
    for obj in objects:
        if isinstance(obj, dict):
            normalized_objects.append({
                "type": str(obj.get("type", "unknown")).strip() or "unknown",
                "count": obj.get("count"),
                "notes": str(obj.get("notes", "")).strip(),
            })
        elif isinstance(obj, str) and obj.strip():
            normalized_objects.append({"type": obj.strip(), "count": None, "notes": ""})

    events = _normalize_list_field(data, "events")
    normalized_events = []
    for event in events:
        if isinstance(event, dict):
            normalized_events.append({
                "type": str(event.get("type", "observation")).strip() or "observation",
                "description": str(event.get("description", "")).strip(),
                "severity": str(event.get("severity", "unknown")).strip() or "unknown",
            })
        elif isinstance(event, str) and event.strip():
            normalized_events.append({
                "type": "observation",
                "description": event.strip(),
                "severity": "unknown",
            })

    attributes = data.get("attributes")
    if not isinstance(attributes, dict):
        attributes = {}

    return {
        "scene_summary": str(data.get("scene_summary", "")).strip(),
        "objects": normalized_objects,
        "actions": [str(a).strip() for a in _normalize_list_field(data, "actions") if str(a).strip()],
        "events": normalized_events,
        "hazards": [str(h).strip() for h in _normalize_list_field(data, "hazards") if str(h).strip()],
        "attributes": {str(k): str(v) for k, v in attributes.items()},
    }


def build_dense_caption(data: Dict[str, Any]) -> str:
    """Short canonical text optimized for passage embedding."""
    parts: List[str] = []
    summary = data.get("scene_summary", "").strip()
    if summary:
        parts.append(summary)

    object_bits = []
    for obj in data.get("objects", []):
        if not isinstance(obj, dict):
            continue
        label = obj.get("type", "object")
        count = obj.get("count")
        notes = obj.get("notes", "")
        if count is not None:
            try:
                count_i = int(count)
                piece = f"{count_i} {label}"
            except (TypeError, ValueError):
                piece = str(label)
        else:
            piece = str(label)
        if notes:
            piece = f"{piece} ({notes})"
        object_bits.append(piece)
    if object_bits:
        parts.append("Objects: " + ", ".join(object_bits[:8]))

    actions = data.get("actions", [])
    if actions:
        parts.append("Actions: " + "; ".join(actions[:6]))

    events = data.get("events", [])
    event_bits = []
    for event in events[:4]:
        if isinstance(event, dict) and event.get("description"):
            event_bits.append(event["description"])
    if event_bits:
        parts.append("Events: " + "; ".join(event_bits))

    hazards = data.get("hazards", [])
    if hazards:
        parts.append("Hazards: " + "; ".join(hazards[:4]))

    caption = " | ".join(parts).strip()
    if len(caption) > DENSE_CAPTION_MAX_CHARS:
        caption = caption[: DENSE_CAPTION_MAX_CHARS - 3].rstrip() + "..."
    return caption or summary or "Video segment"


def build_reasoning_narrative(data: Dict[str, Any]) -> str:
    """Human-readable summary for UI display."""
    lines: List[str] = []
    summary = data.get("scene_summary", "").strip()
    if summary:
        lines.append(summary)

    objects = data.get("objects", [])
    if objects:
        lines.append("Objects:")
        for obj in objects[:10]:
            if isinstance(obj, dict):
                label = obj.get("type", "object")
                count = obj.get("count")
                notes = obj.get("notes", "")
                detail = f"- {label}"
                if count is not None:
                    detail += f" (count: {count})"
                if notes:
                    detail += f": {notes}"
                lines.append(detail)

    actions = data.get("actions", [])
    if actions:
        lines.append("Actions:")
        for action in actions[:8]:
            lines.append(f"- {action}")

    events = data.get("events", [])
    if events:
        lines.append("Events:")
        for event in events[:6]:
            if isinstance(event, dict):
                desc = event.get("description", "")
                severity = event.get("severity", "unknown")
                if desc:
                    lines.append(f"- [{severity}] {desc}")

    hazards = data.get("hazards", [])
    if hazards:
        lines.append("Hazards:")
        for hazard in hazards[:6]:
            lines.append(f"- {hazard}")

    return "\n".join(lines).strip() or summary or "Video segment analysis"


def process_vlm_response(raw_content: str) -> Dict[str, Any]:
    """
    Parse raw VLM text into structured fields.

    Returns dict with: vlm_structured (JSON str), dense_caption, reasoning_content, structured_parse_ok
    """
    try:
        parsed = _coerce_structured(extract_json_object(raw_content))
        dense = build_dense_caption(parsed)
        narrative = build_reasoning_narrative(parsed)
        return {
            "vlm_structured": json.dumps(parsed, ensure_ascii=False),
            "dense_caption": dense,
            "reasoning_content": narrative,
            "structured_parse_ok": True,
        }
    except (json.JSONDecodeError, ValueError, TypeError) as e:
        logger.warning(f"[STRUCTURED] Failed to parse VLM JSON: {e}")
        fallback = raw_content.strip()
        return {
            "vlm_structured": "",
            "dense_caption": fallback[:DENSE_CAPTION_MAX_CHARS],
            "reasoning_content": fallback,
            "structured_parse_ok": False,
        }
