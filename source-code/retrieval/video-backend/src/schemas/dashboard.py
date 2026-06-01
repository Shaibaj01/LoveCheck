"""Dashboard API schemas."""
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class CountItem(BaseModel):
    label: str
    count: int


class ObjectStatItem(BaseModel):
    label: str
    segment_count: int


class UploadDayItem(BaseModel):
    date: str
    segment_rows: int


class DashboardOverview(BaseModel):
    total_rows: int
    segment_rows: int
    video_summary_rows: int
    other_rows: int
    unique_videos: int
    duplicate_segment_slots: int
    duplicate_segment_rows: int
    public_segment_rows: int
    private_segment_rows: int


class DashboardQuality(BaseModel):
    structured_parse_ok: int
    structured_parse_ok_pct: float
    perception_ok: int
    perception_ok_pct: float
    with_object_classes: int
    with_object_classes_pct: float


class RecentVideoItem(BaseModel):
    original_video: str
    filename: str
    segment_rows: int
    unique_segments: int
    expected_segments: int
    duplicate_rows: int
    upload_timestamp: Optional[str] = None
    camera_id: str
    capture_type: str
    location: str
    is_public: bool


class DashboardStatsResponse(BaseModel):
    table: str
    table_available: bool = True
    table_message: Optional[str] = None
    generated_at: str
    query_time_ms: float
    scope: str = Field(default="all", description="all | mine | public")
    overview: DashboardOverview
    quality: DashboardQuality
    objects: List[ObjectStatItem]
    metadata: Dict[str, List[CountItem]]
    uploads_by_day: List[UploadDayItem]
    recent_videos: List[RecentVideoItem]
