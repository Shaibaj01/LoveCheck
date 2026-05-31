import json
import logging
import re
from typing import Dict, Any, Optional

SCENE_SUMMARY_RE = re.compile(
    r'"scene_summary"\s*:\s*"((?:\\.|[^"\\])*)"',
    re.DOTALL,
)


def parse_reasoning_event(event_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Parse reasoning event data from video-reasoner
    
    Args:
        event_data: Raw event data from VastEvent (CloudEvent from video-reasoner)
    
    Returns:
        Parsed reasoning event dict
    """
    logging.info(f"[PARSER] Parsing reasoning event: {event_data}")
    
    # Validate required fields
    required_fields = ["source", "filename"]
    for field in required_fields:
        if field not in event_data:
            raise ValueError(f"Missing required field '{field}' in reasoning event")

    dense = (event_data.get("dense_caption") or "").strip()
    reasoning = (event_data.get("reasoning_content") or "").strip()
    if not dense and not reasoning:
        raise ValueError("Missing dense_caption or reasoning_content in reasoning event")
    
    logging.info(
        f"[PARSER] Parsed reasoning event - filename: {event_data['filename']}, "
        f"dense_caption={len(dense)} chars, reasoning={len(reasoning)} chars"
    )
    
    return event_data


def _extract_scene_summary(text: str) -> Optional[str]:
    if not text or not text.strip():
        return None
    cleaned = text.strip()
    fence_match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", cleaned, re.IGNORECASE)
    if fence_match:
        cleaned = fence_match.group(1)
    match = SCENE_SUMMARY_RE.search(cleaned)
    if not match:
        return None
    raw_value = match.group(1)
    try:
        return str(json.loads(f'"{raw_value}"')).strip()
    except json.JSONDecodeError:
        return raw_value.replace('\\"', '"').replace("\\n", " ").strip()


def _looks_like_json_blob(text: str) -> bool:
    stripped = (text or "").strip()
    return stripped.startswith("```") or stripped.startswith("{") or '"scene_summary"' in stripped[:800]


def resolve_embed_text(
    dense_caption: str,
    reasoning_content: str,
    vlm_structured: str = "",
) -> str:
    """Plain caption text for Cosmos-Embed1; never raw ```json blobs."""
    if vlm_structured and str(vlm_structured).strip():
        try:
            data = json.loads(vlm_structured)
            if isinstance(data, dict):
                summary = str(data.get("scene_summary") or "").strip()
                if summary:
                    return summary
        except Exception:
            pass

    for candidate in ((dense_caption or "").strip(), (reasoning_content or "").strip()):
        if not candidate:
            continue
        if _looks_like_json_blob(candidate):
            summary = _extract_scene_summary(candidate)
            if summary:
                return summary
            continue
        return candidate
    return ""


def validate_embed_text(dense_caption: str, reasoning_content: str) -> bool:
    """Validate text available for embedding (prefer dense_caption)."""
    text = resolve_embed_text(dense_caption, reasoning_content)
    if not text:
        logging.warning("[VALIDATOR] No dense_caption or reasoning_content to embed")
        return False
    logging.info(f"[VALIDATOR] Embed text valid ({len(text)} characters)")
    return True

