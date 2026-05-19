import logging
from typing import Dict, Any


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


def validate_embed_text(dense_caption: str, reasoning_content: str) -> bool:
    """Validate text available for embedding (prefer dense_caption)."""
    text = (dense_caption or "").strip() or (reasoning_content or "").strip()
    if not text:
        logging.warning("[VALIDATOR] No dense_caption or reasoning_content to embed")
        return False
    logging.info(f"[VALIDATOR] Embed text valid ({len(text)} characters)")
    return True

