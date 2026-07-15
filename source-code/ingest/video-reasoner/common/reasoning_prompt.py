"""Plain-text reasoning prompt builder and response normalizer."""
import json
import re
from typing import Any, Dict

REASONING_CONTENT_MAX_CHARS = 1024

_PLAIN_TEXT_INSTRUCTION = (
    "Respond in plain prose only (no JSON, no markdown, no bullet lists). "
    f"Keep your answer under {REASONING_CONTENT_MAX_CHARS} characters.\n"
    "Write a dense, searchable description of what is clearly visible. "
    "Prefer concrete searchable atoms when you can see them: "
    "colors; brand or logo names; vehicle type (and color if clear); "
    "readable street, shop, or sign text; exact counts only when obvious; "
    "the main action underway; the most likely next move if strongly implied. "
    "Mention only what the clip shows — do not invent brands, streets, counts, "
    "or futures that are not evident. Skip filler (weather, 'urban setting', "
    "'no hazards') unless it is the main point of the clip."
)

_SCENE_SUMMARY_RE = re.compile(
    r'"scene_summary"\s*:\s*"((?:\\.|[^"\\])*)"',
    re.DOTALL | re.IGNORECASE,
)
_JSON_FENCE_RE = re.compile(r"```(?:json)?\s*([\s\S]*?)\s*```", re.IGNORECASE)


def build_reasoning_prompt(scene_prompt: str, object_classes: str = "") -> str:
    """Combine scenario prompt with YOLO object hints and plain-text instructions."""
    parts = [scene_prompt.strip()]
    classes = _normalize_class_list(object_classes)
    if classes:
        parts.append(f"Detected objects in this clip: {classes}.")
    parts.append(_PLAIN_TEXT_INSTRUCTION)
    return "\n\n".join(parts)


def normalize_reasoning_content(raw: str) -> str:
    """Return plain text only: strip JSON/markdown fences and truncate."""
    text = (raw or "").strip()
    if not text:
        return ""

    fence_match = _JSON_FENCE_RE.search(text)
    if fence_match:
        text = fence_match.group(1).strip()

    if text.startswith("{"):
        text = _plain_from_json(text) or text

    summary_match = _SCENE_SUMMARY_RE.search(text)
    if summary_match:
        try:
            text = str(json.loads(f'"{summary_match.group(1)}"')).strip()
        except json.JSONDecodeError:
            text = summary_match.group(1).replace('\\"', '"').strip()

    text = _JSON_FENCE_RE.sub("", text)
    text = text.replace("```", "").strip()
    text = re.sub(r"\s+", " ", text).strip()

    return _truncate(text)


def _normalize_class_list(object_classes: str) -> str:
    classes: list[str] = []
    for part in str(object_classes or "").split(","):
        name = part.strip().lower()
        if name and name not in classes:
            classes.append(name)
    return ", ".join(classes)


def _plain_from_json(text: str) -> str:
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return ""
    if not isinstance(data, dict):
        return ""
    summary = str(data.get("scene_summary") or "").strip()
    if summary:
        return summary
    return _flatten_structured_dict(data)


def _flatten_structured_dict(data: Dict[str, Any]) -> str:
    parts: list[str] = []
    for key in ("scene_summary", "summary", "description"):
        value = str(data.get(key) or "").strip()
        if value:
            parts.append(value)
            break
    actions = data.get("actions") or []
    if isinstance(actions, list) and actions:
        parts.append("; ".join(str(a).strip() for a in actions if str(a).strip()))
    return ". ".join(p for p in parts if p).strip()


def _truncate(text: str) -> str:
    if len(text) <= REASONING_CONTENT_MAX_CHARS:
        return text
    cut = text[:REASONING_CONTENT_MAX_CHARS]
    if " " in cut:
        cut = cut.rsplit(" ", 1)[0]
    return cut.rstrip(".,;:") + "..."
