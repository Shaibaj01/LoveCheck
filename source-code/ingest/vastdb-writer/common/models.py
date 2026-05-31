import os
import json
from typing import Any, Optional, Dict, List
from pydantic import BaseModel


class Settings(BaseModel):
    """Configuration settings for VastDB writer"""
    # VastDB settings
    vdbendpoint: str
    vdbbucket: str
    vdbschema: str
    vdbaccesskey: str
    vdbsecretkey: str
    vdbcollection: str
    
    # For schema definition
    embeddingdimensions: int
    embeddingmodel: str
    visual_embedding_dimensions: int = 0
    
    @classmethod
    def from_ctx_secrets(cls, secrets: Dict[str, str]) -> 'Settings':
        """Load settings from runtime context secrets (uses defaults for missing keys)."""
        raw = secrets["vss2-secret"]
        config = {field: raw[field] for field in cls.__annotations__.keys() if field in raw}
        return cls(**config)


class EmbeddingEvent(BaseModel):
    """Event data from reasoning-embedder"""
    source: str
    filename: str
    reasoning_content: str
    dense_caption: str | None = None
    vlm_structured: str | None = None
    structured_parse_ok: bool = False
    embedding: List[float]
    embedding_model: str
    embedding_dimensions: int
    visual_embedding: List[float] = []
    visual_embedding_model: str = ""
    visual_embedding_dimensions: int = 0
    visual_embedding_ok: bool = False
    cosmos_model: str
    tokens_used: int
    cached_prompt_tokens: int = 0
    processing_time: float
    status: str = "success"
    
    # Metadata fields (from pipeline)
    is_public: bool = True  # Default to public (CLI uploads)
    allowed_users: str | None = None  # Empty for CLI uploads
    tags: str | None = None
    upload_timestamp: str | None = None
    segment_number: int | None = None
    total_segments: int | None = None
    segment_duration: float | None = None
    segment_start_sec: float | None = None
    segment_end_sec: float | None = None
    original_video: str | None = None

    perception_json: str | None = None
    object_classes: str | None = None
    object_counts: str | None = None
    max_detection_conf: float | None = None
    perception_ok: bool = False
    row_kind: str = "segment"
    video_summary_json: str | None = None
    video_events_json: str | None = None

    # Stream capture metadata (from video-streaming service)
    camera_id: str | None = None
    capture_type: str | None = None
    location: str | None = None

