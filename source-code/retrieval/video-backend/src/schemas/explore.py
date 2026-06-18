"""Explore browse and on-demand chunk synthesis schemas."""
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field

from src.models.video import ChunkSearchResult


class ExploreUploadDay(BaseModel):
    date: str
    chunk_count: int


class ExploreResponse(BaseModel):
    chunks: List[ChunkSearchResult]
    total: int
    uploads_by_day: List[ExploreUploadDay]
    scope: str
    selected_date: Optional[str] = None
    limit: int
    offset: int
    table_available: bool = True
    table_message: Optional[str] = None


class VideoSynthesizeRequest(BaseModel):
    original_video: str = Field(..., min_length=1)
    question: str = Field(
        default="Summarize what happened in this entire video chronologically.",
        min_length=1,
    )
    max_segments: int = Field(default=50, ge=1, le=100)
    system_prompt: Optional[str] = None


class VideoSynthesizeResponse(BaseModel):
    original_video: str
    segment_count: int
    segments_used: int
    answer: str
    llm_synthesis: dict
    generated_at: datetime
