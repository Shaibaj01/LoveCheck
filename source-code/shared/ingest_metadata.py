"""
Single source of truth for ingest/upload metadata field definitions.

Consumed by: video-backend, video-streaming, video-batch-sync, video-frontend (via API).
Prompt text for analysis scenarios remains in ingest/video-reasoner/common/prompts.py.
"""
from __future__ import annotations

from typing import Any, Dict, List, Mapping, Optional
from urllib.parse import quote

CUSTOM_PROMPT_MAX_LENGTH = 800

FILTERABLE_METADATA_COLUMNS = ("camera_id", "capture_type", "location", "object_classes")

METADATA_FIELD_LABELS: Dict[str, str] = {
    "camera_id": "Camera ID",
    "capture_type": "Capture Type",
    "location": "Location",
    "object_classes": "Object class",
}

PLACEHOLDERS: Dict[str, str] = {
    "camera_id": "e.g., CAM-001, manhattan-cam-1",
    "location": "e.g., Midtown, Downtown, Times Square",
    "tags": "demo, outdoor, test",
    "allowed_users": "john.doe, jane.smith",
    "custom_prompt": "Enter your custom reasoning prompt for the AI model...",
}

CAPTURE_TYPE_DEFAULT_LABEL = "-- Select Type --"

CAPTURE_TYPES: List[Dict[str, str]] = [
    {"value": "traffic", "label": "Traffic"},
    {"value": "streets", "label": "Streets"},
    {"value": "crowds", "label": "Crowds"},
    {"value": "malls", "label": "Malls"},
    {"value": "general", "label": "General"},
    {"value": "sports", "label": "Sports"},
    {"value": "robotics", "label": "Robotics"},
    {"value": "warehouse", "label": "Warehouse"},
    {"value": "retail", "label": "Retail"},
]

ANALYSIS_SCENARIO_DEFAULT_LABEL = "-- Use Default (from settings) --"

# UI labels only — keys must exist in video-reasoner SCENARIO_PROMPTS (prompts.py).
ANALYSIS_SCENARIO_LABELS: List[Dict[str, str]] = [
    {"value": "surveillance", "label": "Incident & Safety Detection"},
    {"value": "traffic", "label": "Vehicle & Pedestrian Monitoring"},
    {"value": "live_driving", "label": "Live Driving & Road Safety"},
    {"value": "nhl", "label": "Hockey Game Analysis"},
    {"value": "sports", "label": "General Sports Analysis"},
    {"value": "retail", "label": "Retail Store Monitoring"},
    {"value": "warehouse", "label": "Warehouse Safety & Operations"},
    {"value": "nyc_control", "label": "NYC Traffic & Public Safety"},
    {"value": "nyc_safety_surveillance", "label": "NYC Street Safety Surveillance"},
    {"value": "egocentric", "label": "First-Person Activity Analysis"},
    {"value": "general", "label": "General Video Analysis"},
]

USE_CUSTOM_PROMPT_LABEL = "Use custom prompt (overrides scenario)"
METADATA_SECTION_TITLE = "Stream Metadata (Optional)"
METADATA_SECTION_DESCRIPTION = (
    "These fields will be stored with each video segment for filtering and search"
)

# Internal form/API key -> S3 object metadata key (kebab-case).
S3_METADATA_KEY_MAP: Dict[str, str] = {
    "camera_id": "camera-id",
    "capture_type": "capture-type",
    "location": "location",
    "scenario": "scenario",
    "custom_prompt": "custom-prompt",
    "tags": "tags",
    "allowed_users": "allowed-users",
    "is_public": "is-public",
    "original_filename": "original-filename",
    "upload_timestamp": "upload-timestamp",
    "capture_timestamp": "capture-timestamp",
    "owner": "owner",
}


def parse_comma_list(value: Optional[str]) -> List[str]:
    if not value or not str(value).strip():
        return []
    return [part.strip() for part in str(value).split(",") if part.strip()]


def truncate_custom_prompt(value: Optional[str]) -> Optional[str]:
    if not value or not str(value).strip():
        return None
    return str(value).strip()[:CUSTOM_PROMPT_MAX_LENGTH]


def build_s3_ingest_metadata(
    *,
    camera_id: Optional[str] = None,
    capture_type: Optional[str] = None,
    location: Optional[str] = None,
    scenario: Optional[str] = None,
    custom_prompt: Optional[str] = None,
    tags: Optional[List[str]] = None,
    allowed_users: Optional[List[str]] = None,
    is_public: Optional[bool] = None,
    original_filename: Optional[str] = None,
    upload_timestamp: Optional[str] = None,
    capture_timestamp: Optional[str] = None,
    owner: Optional[str] = None,
    extra: Optional[Mapping[str, str]] = None,
) -> Dict[str, str]:
    """Build S3 UserDefined metadata dict from ingest field values."""
    out: Dict[str, str] = {}

    def _set(field: str, raw: Optional[str]) -> None:
        if raw is None:
            return
        text = str(raw).strip()
        if not text:
            return
        s3_key = S3_METADATA_KEY_MAP.get(field, field)
        out[s3_key] = text

    _set("camera_id", camera_id)
    _set("capture_type", capture_type)
    _set("location", location)
    _set("scenario", scenario)

    prompt = truncate_custom_prompt(custom_prompt)
    if prompt:
        out[S3_METADATA_KEY_MAP["custom_prompt"]] = quote(prompt, safe="")

    if tags:
        joined = ",".join(t.strip() for t in tags if t and str(t).strip())
        if joined:
            out[S3_METADATA_KEY_MAP["tags"]] = joined

    if allowed_users:
        joined = ",".join(u.strip() for u in allowed_users if u and str(u).strip())
        if joined:
            out[S3_METADATA_KEY_MAP["allowed_users"]] = joined

    if is_public is not None:
        out[S3_METADATA_KEY_MAP["is_public"]] = "true" if is_public else "false"

    _set("original_filename", original_filename)
    _set("upload_timestamp", upload_timestamp)
    _set("capture_timestamp", capture_timestamp)
    _set("owner", owner)

    if extra:
        for key, val in extra.items():
            if val is not None and str(val).strip():
                out[key] = str(val).strip()

    return out


def ingest_config_for_api() -> Dict[str, Any]:
    """Payload for GET /api/v1/metadata/ingest-config."""
    return {
        "custom_prompt_max_length": CUSTOM_PROMPT_MAX_LENGTH,
        "filterable_fields": [
            {"key": key, "label": METADATA_FIELD_LABELS[key]}
            for key in FILTERABLE_METADATA_COLUMNS
        ],
        "capture_types": CAPTURE_TYPES,
        "capture_type_default_label": CAPTURE_TYPE_DEFAULT_LABEL,
        "analysis_scenarios": ANALYSIS_SCENARIO_LABELS,
        "analysis_scenario_default_label": ANALYSIS_SCENARIO_DEFAULT_LABEL,
        "labels": {
            "use_custom_prompt": USE_CUSTOM_PROMPT_LABEL,
            "metadata_section_title": METADATA_SECTION_TITLE,
            "metadata_section_description": METADATA_SECTION_DESCRIPTION,
            **METADATA_FIELD_LABELS,
        },
        "placeholders": PLACEHOLDERS,
    }
