export const BASE_PATH = "/app";

export type Camera = {
  id: string;
  label: string;
  camera_id: string;
  source: string;
  start_sec: number;
  ok: boolean;
};

export type AlertItem = {
  id: string;
  kind: string;
  label: string;
  card_id: string;
  summary: string;
  source: string;
  start_sec: number;
};

export function apiUrl(path: string): string {
  return `${BASE_PATH}${path}`;
}

export function clipUrl(source: string): string {
  return apiUrl(`/api/clip?source=${encodeURIComponent(source)}`);
}
