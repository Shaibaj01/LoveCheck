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


class S3Inventory(BaseModel):
    chunks_bucket: str
    chunks_mp4: Optional[int] = None
    segments_bucket: str
    segments_mp4: Optional[int] = None
    segmenter_output_bucket: str
    segmenter_output_mp4: Optional[int] = None
    errors: Optional[Dict[str, str]] = None


class PipelineAlignment(BaseModel):
    segments_s3_mp4: Optional[int] = None
    indexed_clips: int = 0
    segment_rows: int = 0
    pending_index: Optional[int] = None
    re_ingest_excess: int = 0
    indexed_matches_segments_s3: Optional[bool] = None
    rows_match_segments_s3: Optional[bool] = None
    segments_bucket_matches_segmenter: Optional[bool] = None
    healthy: Optional[bool] = None


class DashboardOverview(BaseModel):
    total_rows: int
    segment_rows: int
    other_rows: int
    unique_videos: int
    indexed_clips: int = 0
    re_ingest_rows: int = 0
    re_ingest_clips: int = 0
    stream_sessions: int = 0
    duplicate_segment_slots: int = 0
    duplicate_segment_rows: int = 0
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
    stream_id: Optional[str] = None
    segment_rows: int
    indexed_clips: int = 0
    chunk_count: int = 0
    re_ingest_rows: int = 0
    stream_span_sec: Optional[float] = None
    ingest_kind: Optional[str] = None
    unique_segments: int = 0
    expected_segments: int = 0
    duplicate_rows: int = 0
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
    s3_inventory: Optional[S3Inventory] = None
    pipeline_alignment: Optional[PipelineAlignment] = None
