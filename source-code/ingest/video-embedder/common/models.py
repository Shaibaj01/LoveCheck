import os
import json
from typing import Any, Optional, Dict, List
from pydantic import BaseModel


class Settings(BaseModel):
    """Configuration settings for reasoning embedder"""
    # S3 (segment download for visual embeddings)
    s3accesskey: str
    s3secretkey: str
    s3endpoint: str

    # Text embedding: openai_compat (Llama embed NIM) or cosmos_embed1 (Cosmos-Embed1 NIM)
    embedding_provider: str = ""
    embeddinghost: str
    embeddingport: int
    embeddinghttpscheme: str = "http"
    embedding_local_nim: bool = False
    embeddingmodel: str
    embeddingdimensions: int
    nvidia_api_key: Optional[str] = None

    # Visual embedding settings (multimodal NIM)
    visual_embedding_enabled: bool = True
    visual_embedding_model: str = "nvidia/llama-3.2-nemoretriever-1b-vlm-embed-v1"
    visual_embedding_dimensions: int = 256
    visual_embedding_host: str = ""
    visual_embedding_port: int = 0
    visual_embedding_httpscheme: str = ""
    visual_embedding_local_nim: bool = False
    visual_embedding_num_frames: int = 3
    
    @classmethod
    def from_ctx_secrets(cls, secrets: Dict[str, str]) -> 'Settings':
        """Load settings from runtime context secrets (uses model defaults for missing optional fields)"""
        raw = secrets["videoreasonsecret"]
        config = {field: raw[field] for field in cls.__annotations__.keys() if field in raw}
        if not config.get("visual_embedding_host"):
            config["visual_embedding_host"] = config.get("embeddinghost", "")
        if not config.get("visual_embedding_port"):
            config["visual_embedding_port"] = config.get("embeddingport", 443)
        if not config.get("visual_embedding_httpscheme"):
            config["visual_embedding_httpscheme"] = config.get("embeddinghttpscheme", "https")
        if "visual_embedding_local_nim" not in config and "embedding_local_nim" in config:
            config["visual_embedding_local_nim"] = config["embedding_local_nim"]
        return cls(**config)


class ReasoningEvent(BaseModel):
    """Event data from video-reasoner"""
    source: str
    filename: str
    reasoning_content: str
    dense_caption: str | None = None
    vlm_structured: str | None = None
    structured_parse_ok: bool = False
    cosmos_model: str
    tokens_used: int
    cached_prompt_tokens: int = 0
    processing_time: float
    video_url: str
    status: str = "success"
    
    # Metadata fields (passed through pipeline)
    is_public: bool = True  # Default to public (CLI uploads)
    allowed_users: str | None = None
    tags: str | None = None
    upload_timestamp: str | None = None
    segment_number: int | None = None
    total_segments: int | None = None
    segment_duration: float | None = None
    segment_start_sec: float | None = None
    segment_end_sec: float | None = None
    original_video: str | None = None

    # Stream capture metadata (from video-streaming service)
    camera_id: str | None = None
    capture_type: str | None = None
    location: str | None = None
    
    # Analysis scenario metadata
    scenario: str | None = None

    perception_json: str | None = None
    object_classes: str | None = None
    object_counts: str | None = None
    max_detection_conf: float | None = None
    perception_ok: bool = False
    row_kind: str = "segment"

    # Perception lite
    perception_json: str | None = None
    object_classes: str | None = None
    object_counts: str | None = None
    max_detection_conf: float | None = None
    perception_ok: bool = False
    row_kind: str = "segment"


class EmbeddingResult(BaseModel):
    """Result from embedding generation"""
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
    video_url: str
    status: str = "success"
    
    # Metadata fields (passed to vastdb-writer)
    is_public: bool = True  # Default to public (CLI uploads)
    allowed_users: str | None = None
    tags: str | None = None
    upload_timestamp: str | None = None
    segment_number: int | None = None
    total_segments: int | None = None
    segment_duration: float | None = None
    segment_start_sec: float | None = None
    segment_end_sec: float | None = None
    original_video: str | None = None
    
    # Stream capture metadata (from video-streaming service)
    camera_id: str | None = None
    capture_type: str | None = None
    location: str | None = None
    
    # Analysis scenario metadata
    scenario: str | None = None

    perception_json: str | None = None
    object_classes: str | None = None
    object_counts: str | None = None
    max_detection_conf: float | None = None
    perception_ok: bool = False
    row_kind: str = "segment"

