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
    
    required_fields = ["source", "filename"]
    for field in required_fields:
        if field not in event_data:
            raise ValueError(f"Missing required field '{field}' in reasoning event")

    reasoning = (event_data.get("reasoning_content") or "").strip()
    if not reasoning:
        raise ValueError("Missing reasoning_content in reasoning event")
    
    logging.info(
        f"[PARSER] Parsed reasoning event - filename: {event_data['filename']}, "
        f"reasoning={len(reasoning)} chars"
    )
    
    return event_data


def resolve_embed_text(reasoning_content: str) -> str:
    """Plain caption text for Cosmos-Embed1 from normalized reasoning_content."""
    return (reasoning_content or "").strip()


def validate_embed_text(reasoning_content: str) -> bool:
    """Validate text available for embedding."""
    text = resolve_embed_text(reasoning_content)
    if not text:
        logging.warning("[VALIDATOR] No reasoning_content to embed")
        return False
    logging.info(f"[VALIDATOR] Embed text valid ({len(text)} characters)")
    return True
