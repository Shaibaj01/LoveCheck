export const BASE_PATH = "/app";

export type TimeFilter = "1h" | "24h" | "7d" | "all";

export type Camera = {
  id: string;
  label: string;
  camera_id: string;
  source: string;
  start_sec: number;
  duration_sec?: number;
  reasoning: string;
  ok: boolean;
};

export type AlertItem = {
  id: string;
  kind: string;
  label: string;
  card_id: string;
  camera_id: string;
  site: string;
  camera_label: string;
  title: string;
  summary: string;
  source: string;
  start_sec: number;
  end_sec: number;
  duration_sec: number;
  score: number;
  upload_timestamp: string;
};

export type FeedSummary = {
  kind: string;
  label: string;
  card_id: string;
  text: string;
};

export function apiUrl(path: string): string {
  return `${BASE_PATH}${path}`;
}

export function clipUrl(source: string): string {
  return apiUrl(`/api/clip?source=${encodeURIComponent(source)}`);
}

export function withWindow(
  path: string,
  timeFilter: TimeFilter,
  date: string,
  q?: string
): string {
  const params = new URLSearchParams();
  if (date) params.set("date", date);
  else params.set("time_filter", timeFilter);
  if (q) params.set("q", q);
  const qs = params.toString();
  return apiUrl(`${path}${qs ? `?${qs}` : ""}`);
}
