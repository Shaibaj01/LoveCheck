import logging
from typing import Dict, Any


def parse_embedding_event(event_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Parse embedding event data from reasoning-embedder
    
    Args:
        event_data: Raw event data from VastEvent (CloudEvent from reasoning-embedder)
    
    Returns:
        Parsed embedding event dict
    """
    if event_data.get("status") == "error":
        raise ValueError(f"Upstream embedding error: {event_data.get('error', 'unknown')}")

    if event_data.get("status") == "skipped":
        raise ValueError(f"Upstream skipped: {event_data.get('reason', 'unknown')}")

    logging.info(
        f"[PARSER] Parsing embedding event: "
        f"filename={event_data.get('filename')} source={event_data.get('source')}"
    )
    
    # Validate required fields
    required_fields = ["source", "filename", "reasoning_content", "embedding"]
    for field in required_fields:
        if field not in event_data:
            raise ValueError(f"Missing required field '{field}' in embedding event")
    
    logging.info(f"[PARSER] Parsed embedding event - filename: {event_data['filename']}, embedding_dims: {len(event_data.get('embedding', []))}")
    
    return event_data


def validate_embedding(embedding: list) -> bool:
    """
    Validate embedding vector is not empty
    
    Args:
        embedding: The embedding vector
    
    Returns:
        True if valid, False otherwise
    """
    if not embedding or len(embedding) == 0:
        logging.warning("[VALIDATOR] Embedding vector is empty")
        return False
    
    logging.info(f"[VALIDATOR] Embedding vector is valid ({len(embedding)} dimensions)")
    return True

