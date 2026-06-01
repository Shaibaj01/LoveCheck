export interface CountItem {
  label: string;
  count: number;
}

export interface ObjectStatItem {
  label: string;
  segment_count: number;
}

export interface UploadDayItem {
  date: string;
  segment_rows: number;
}

export interface DashboardOverview {
  total_rows: number;
  segment_rows: number;
  video_summary_rows: number;
  other_rows: number;
  unique_videos: number;
  duplicate_segment_slots: number;
  duplicate_segment_rows: number;
  public_segment_rows: number;
  private_segment_rows: number;
}

export interface DashboardQuality {
  structured_parse_ok: number;
  structured_parse_ok_pct: number;
  perception_ok: number;
  perception_ok_pct: number;
  with_object_classes: number;
  with_object_classes_pct: number;
}

export interface RecentVideoItem {
  original_video: string;
  filename: string;
  segment_rows: number;
  unique_segments: number;
  expected_segments: number;
  duplicate_rows: number;
  upload_timestamp?: string | null;
  camera_id: string;
  capture_type: string;
  location: string;
  is_public: boolean;
}

export interface DashboardStatsResponse {
  table: string;
  table_available: boolean;
  table_message?: string | null;
  generated_at: string;
  query_time_ms: number;
  scope: string;
  overview: DashboardOverview;
  quality: DashboardQuality;
  objects: ObjectStatItem[];
  metadata: Record<string, CountItem[]>;
  uploads_by_day: UploadDayItem[];
  recent_videos: RecentVideoItem[];
}

export type DashboardScope = 'all' | 'mine' | 'public';
