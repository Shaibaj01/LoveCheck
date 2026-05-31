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
  "scene_summary": "one short sentence, max 25 words — setting + main activity only",
  "objects": [{"type": "string", "count": 1, "notes": "optional visible details"}],
  "actions": ["observed activity phrases, e.g. speaking to camera, walking across frame"],
  "events": [{"type": "string", "description": "string", "severity": "low|medium|high|unknown"}],
  "hazards": ["safety or risk observations, empty array if none"],
  "attributes": {"setting": "optional key-value context"}
}

Rules:
- Describe only what is visible in this clip; do not guess or invent details.
- scene_summary must stay brief; put entity lists in objects, verbs in actions, scene-level notes in events.
- objects: REQUIRED — list every distinct visible entity (people, vehicles, equipment, animals, signage).
- actions: REQUIRED — at least one observable activity when anything moves or interacts.
- events: include scene-level observations (filming, crowd flow, interview, traffic) when visible; [] only for a static empty scene.
- hazards: [] when none visible.
"""

DENSE_CAPTION_MAX_CHARS = 600
OBJECT_NOTES_MAX_CHARS = 120


def wrap_prompt_with_structured_output(base_prompt: str) -> str:
    """Append JSON output instructions to scenario or custom prompts."""
    base = base_prompt.strip()
    if "Respond with a single JSON object only" in base:
        return base
    return f"{base}\n\n{STRUCTURED_OUTPUT_INSTRUCTION}"


SCENE_SUMMARY_RE = re.compile(
    r'"scene_summary"\s*:\s*"((?:\\.|[^"\\])*)"',
    re.DOTALL,
)


def _strip_json_fences(text: str) -> str:
    cleaned = (text or "").strip()
    fence_match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", cleaned, re.IGNORECASE)
    if fence_match:
        return fence_match.group(1).strip()
    return cleaned


def _repair_json_payload(payload: str) -> str:
    """Fix common VLM JSON mistakes before json.loads."""
    repaired = payload
    repaired = re.sub(
        r'("scene_summary"\s*:\s*"(?:\\.|[^"\\])*")\s*\n(\s*"objects")',
        r"\1,\n\2",
        repaired,
    )
    repaired = re.sub(
        r'("scene_summary"\s*:\s*"(?:\\.|[^"\\])*")\s+("objects")',
        r"\1, \2",
        repaired,
    )
    repaired = re.sub(r'([\}\]])\s*(?!,)(\s*"[\w_]+"\s*:)', r"\1,\2", repaired)
    repaired = re.sub(r"\}\s*\{", "}, {", repaired)
    repaired = re.sub(r",\s*([\}\]])", r"\1", repaired)
    return repaired


def _load_json_object(payload: str) -> Dict[str, Any]:
    """Parse JSON object with progressive repair attempts."""
    last_error: Optional[Exception] = None
    candidates = [payload, _repair_json_payload(payload)]
    if candidates[-1] != candidates[0]:
        candidates.append(_repair_json_payload(candidates[-1]))
    for candidate in candidates:
        try:
            data = json.loads(candidate)
            if not isinstance(data, dict):
                raise ValueError("VLM JSON root must be an object")
            return data
        except (json.JSONDecodeError, ValueError, TypeError) as exc:
            last_error = exc
            continue
    raise last_error or ValueError("Failed to parse VLM JSON")


OBJECT_DICT_RE = re.compile(
    r'\{\s*"type"\s*:\s*"([^"\\]*(?:\\.[^"\\]*)*)"\s*,\s*"count"\s*:\s*(\d+)',
    re.IGNORECASE,
)


def _extract_object_dicts_from_raw(text: str) -> List[Dict[str, Any]]:
    objects: List[Dict[str, Any]] = []
    seen: set[str] = set()
    for match in OBJECT_DICT_RE.finditer(text or ""):
        label = match.group(1).replace('\\"', '"').strip().lower()
        if not label or label in seen:
            continue
        seen.add(label)
        objects.append({"type": label, "count": int(match.group(2)), "notes": ""})
    return objects


SUMMARY_ENTITY_RULES: List[tuple[str, str]] = [
    (r"\bminnie mouse\b", "minnie mouse"),
    (r"\bcherry picker\b", "cherry picker"),
    (r"\bdigital billboards?\b", "signboard"),
    (r"\bbillboards?\b", "signboard"),
    (r"\bpedestrians?\b", "person"),
    (r"\bpeople\b", "person"),
    (r"\bcameraman\b", "person"),
    (r"\bcostumed performers?\b", "person"),
    (r"\bperformers?\b", "person"),
    (r"\bgorillas?\b", "gorilla"),
    (r"\bambulances?\b", "ambulance"),
    (r"\bforklifts?\b", "forklift"),
    (r"\bstatues?\b", "statue"),
    (r"\bcameras?\b", "camera"),
    (r"\btrucks?\b", "truck"),
    (r"\bcranes?\b", "crane"),
    (r"\bstorefronts?\b", "store"),
    (r"\bstores?\b", "store"),
    (r"\bsignboards?\b", "signboard"),
    (r"\bmen\b", "person"),
    (r"\bman\b", "person"),
    (r"\bwomen\b", "person"),
    (r"\bwoman\b", "person"),
]


def _infer_objects_from_summary(summary: str) -> List[Dict[str, Any]]:
    if not summary.strip():
        return []
    lower = summary.lower()
    counts: Dict[str, int] = {}
    for match in re.finditer(r"(\d+)\s+(people|persons|pedestrians|men|women)", lower):
        counts["person"] = counts.get("person", 0) + int(match.group(1))
    for pattern, obj_type in SUMMARY_ENTITY_RULES:
        if re.search(pattern, lower):
            counts[obj_type] = counts.get(obj_type, 0) + 1
    return [
        {"type": label, "count": count, "notes": "inferred from summary"}
        for label, count in sorted(counts.items())
    ]


def _recover_partial_structured(raw_content: str) -> Optional[Dict[str, Any]]:
    summary = extract_scene_summary(raw_content)
    objects = _extract_object_dicts_from_raw(raw_content)
    if not summary and not objects:
        return None
    return {
        "scene_summary": summary or "",
        "objects": objects,
        "actions": [],
        "events": [],
        "hazards": [],
        "attributes": {},
    }


def extract_scene_summary(text: str) -> Optional[str]:
    """Best-effort scene_summary extraction when full JSON parsing fails."""
    if not text or not text.strip():
        return None
    cleaned = _strip_json_fences(text)
    match = SCENE_SUMMARY_RE.search(cleaned)
    if not match:
        return None
    raw_value = match.group(1)
    try:
        return str(json.loads(f'"{raw_value}"')).strip()
    except json.JSONDecodeError:
        return raw_value.replace('\\"', '"').replace("\\n", " ").strip()


def extract_json_object(text: str) -> Dict[str, Any]:
    """Extract and parse the first JSON object from model output."""
    if not text or not text.strip():
        raise ValueError("Empty VLM response")

    cleaned = _strip_json_fences(text.strip())
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("No JSON object found in VLM response")

    payload = cleaned[start : end + 1]
    return _load_json_object(payload)


def _normalize_list_field(data: Dict[str, Any], key: str) -> List[Any]:
    value = data.get(key, [])
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return []


def _coerce_count(value: Any) -> Optional[int]:
    """Normalize object counts; fuzzy strings like 'more than 10' -> 10."""
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, int):
        return max(1, value)
    if isinstance(value, float):
        return max(1, int(value))
    text = str(value).strip()
    if not text:
        return None
    try:
        return max(1, int(text))
    except (TypeError, ValueError):
        match = re.search(r"\d+", text)
        if match:
            return max(1, int(match.group(0)))
    return None


def _truncate_notes(notes: str) -> str:
    text = notes.strip()
    if len(text) <= OBJECT_NOTES_MAX_CHARS:
        return text
    return text[: OBJECT_NOTES_MAX_CHARS - 3].rstrip() + "..."


def _coerce_structured(data: Dict[str, Any]) -> Dict[str, Any]:
    """Ensure expected keys exist with safe types."""
    objects = _normalize_list_field(data, "objects")
    normalized_objects = []
    for obj in objects:
        if isinstance(obj, dict):
            normalized_objects.append({
                "type": str(obj.get("type", "unknown")).strip() or "unknown",
                "count": _coerce_count(obj.get("count")),
                "notes": _truncate_notes(str(obj.get("notes", ""))),
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
        count = _coerce_count(obj.get("count"))
        if count is not None:
            piece = f"{count} {label}"
        else:
            piece = str(label)
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


def merge_perception_into_structured(
    data: Dict[str, Any], perception: Optional[Dict[str, Any]]
) -> Dict[str, Any]:
    """Fill empty object lists from perception lite detections."""
    if not perception or not perception.get("perception_ok"):
        return data

    if not data.get("objects"):
        try:
            counts = json.loads(perception.get("object_counts") or "{}")
        except json.JSONDecodeError:
            counts = {}
        for cls, cnt in sorted(counts.items()):
            try:
                count_i = max(1, int(cnt))
            except (TypeError, ValueError):
                count_i = 1
            data.setdefault("objects", []).append({
                "type": str(cls).strip(),
                "count": count_i,
                "notes": "perception lite",
            })

    summary = (perception.get("perception_summary") or "").strip()
    if summary and not data.get("actions"):
        data.setdefault("actions", []).append(summary)

    return data


def _infer_actions_from_summary(summary: str) -> List[str]:
    if not summary.strip():
        return []
    actions: List[str] = []
    for match in re.finditer(
        r"\b([a-z]+(?:\s+[a-z]+){0,2}\s+(?:ing|ed))\b",
        summary,
        re.IGNORECASE,
    ):
        phrase = match.group(1).strip().lower()
        if len(phrase) > 4:
            actions.append(phrase)
    for match in re.finditer(r"\bwhile\s+([^,;.]+)", summary, re.IGNORECASE):
        phrase = match.group(1).strip().lower()
        if phrase:
            actions.append(phrase)
    return list(dict.fromkeys(actions))[:6]


def _infer_events_from_summary(summary: str) -> List[Dict[str, Any]]:
    if not summary.strip():
        return []
    lower = summary.lower()
    events: List[Dict[str, Any]] = []
    if any(token in lower for token in ("filmed", "camera", "interview", "recording", "broadcast")):
        events.append({
            "type": "media",
            "description": "Filming or on-camera activity",
            "severity": "low",
        })
    if any(token in lower for token in ("crowd", "pedestrian", "plaza", "bustling", "traffic")):
        events.append({
            "type": "crowd",
            "description": "Active public or pedestrian activity",
            "severity": "low",
        })
    return events[:4]


def enrich_sparse_structured(data: Dict[str, Any]) -> Dict[str, Any]:
    """Backfill objects/actions/events when the VLM returns only scene_summary."""
    summary = str(data.get("scene_summary", "")).strip()

    if not data.get("objects"):
        inferred_objects = _infer_objects_from_summary(summary)
        if inferred_objects:
            data["objects"] = inferred_objects

    if not data.get("actions"):
        inferred = _infer_actions_from_summary(summary)
        if inferred:
            data["actions"] = inferred

    if not data.get("events"):
        inferred_events = _infer_events_from_summary(summary)
        if inferred_events:
            data["events"] = inferred_events

    return data


def apply_structured_enrichment(
    data: Dict[str, Any], perception: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    enriched = _coerce_structured(data)
    enriched = merge_perception_into_structured(enriched, perception)
    enriched = enrich_sparse_structured(enriched)
    return enriched


def derive_object_metadata(data: Dict[str, Any]) -> Dict[str, Any]:
    """Build object_classes / object_counts columns from structured objects."""
    counts: Dict[str, int] = {}
    classes: List[str] = []
    for obj in data.get("objects", []):
        if not isinstance(obj, dict):
            continue
        label = str(obj.get("type", "")).strip().lower()
        if not label:
            continue
        try:
            count_i = max(1, _coerce_count(obj.get("count")) or 1)
        except (TypeError, ValueError):
            count_i = 1
        counts[label] = counts.get(label, 0) + count_i
        if label not in classes:
            classes.append(label)
    return {
        "object_classes": ",".join(classes),
        "object_counts": json.dumps(counts, ensure_ascii=False),
    }


def rebuild_vlm_fields(
    data: Dict[str, Any], structured_parse_ok: bool = True
) -> Dict[str, Any]:
    recovered_ok = bool(data.get("scene_summary")) and bool(data.get("objects"))
    return {
        "vlm_structured": json.dumps(data, ensure_ascii=False),
        "dense_caption": build_dense_caption(data),
        "reasoning_content": build_reasoning_narrative(data),
        "structured_parse_ok": structured_parse_ok or recovered_ok,
    }


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


def process_vlm_response(
    raw_content: str, perception: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Parse raw VLM text into structured fields.

    Returns dict with: vlm_structured (JSON str), dense_caption, reasoning_content, structured_parse_ok
    """
    try:
        parsed = apply_structured_enrichment(extract_json_object(raw_content), perception)
        return rebuild_vlm_fields(parsed, structured_parse_ok=True)
    except (json.JSONDecodeError, ValueError, TypeError) as e:
        logger.warning(f"[STRUCTURED] Failed to parse VLM JSON: {e}")
        partial = _recover_partial_structured(raw_content)
        if partial:
            enriched = apply_structured_enrichment(partial, perception)
            logger.info(
                f"[STRUCTURED] Partial recovery: summary={bool(partial.get('scene_summary'))}, "
                f"objects={len(enriched.get('objects', []))}"
            )
            return rebuild_vlm_fields(enriched, structured_parse_ok=False)

        summary = extract_scene_summary(raw_content)
        if summary:
            partial = apply_structured_enrichment(
                {
                    "scene_summary": summary,
                    "objects": [],
                    "actions": [],
                    "events": [],
                    "hazards": [],
                    "attributes": {},
                },
                perception,
            )
            logger.info(f"[STRUCTURED] Recovered scene_summary fallback ({len(summary)} chars)")
            return rebuild_vlm_fields(partial, structured_parse_ok=False)

        fallback = _strip_json_fences(raw_content).strip()
        if fallback.startswith("{"):
            fallback = summary or "Video segment"
        return {
            "vlm_structured": "",
            "dense_caption": (fallback or "Video segment")[:DENSE_CAPTION_MAX_CHARS],
            "reasoning_content": fallback or "Video segment analysis",
            "structured_parse_ok": False,
        }
