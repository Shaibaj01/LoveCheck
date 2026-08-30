from typing import Any, Dict, Tuple
from urllib.parse import unquote

import logging


def parse_s3_event(event_data: Dict[str, Any]) -> Dict[str, str]:
    logging.info(f"[PARSER] Parsing S3 event: {event_data}")
    if "Records" in event_data:
        record = event_data["Records"][0]
        s3_info = record.get("s3", {})
        bucket = s3_info.get("bucket", {}).get("name", "")
        key = s3_info.get("object", {}).get("key", "")
        event_name = record.get("eventName", "unknown")
    elif "bucket" in event_data and "key" in event_data:
        bucket = event_data["bucket"]
        key = event_data["key"]
        event_name = event_data.get("eventName", "unknown")
    else:
        raise ValueError(f"Unsupported event format: {event_data}")
    key = unquote(key)
    return {"bucket": bucket, "key": key, "event_name": event_name}


def should_process_event(key: str, event_name: str) -> Tuple[bool, str]:
    if "Delete" in event_name:
        return False, "Delete event - skipping"
    if not key.lower().endswith(".mp4"):
        return False, f"Not an MP4 file - skipping (key: {key})"
    if not ("_segment_" in key.lower() or "-segment-" in key.lower() or "/segments/" in key.lower()):
        return False, "Not a segment - skipping (only process segments)"
    return True, ""
