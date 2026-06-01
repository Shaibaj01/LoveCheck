export interface KeyEventSuggestion {
  query_text: string;
  label: string;
  original_video: string;
  filename: string;
  segment_start_sec: number;
  segment_end_sec: number;
  generated_at?: string | null;
  batch_id?: string;
}

export interface SuggestionsResponse {
  batch_id: string | null;
  generated_at: string | null;
  search_prompts: string[];
  key_events: KeyEventSuggestion[];
  key_events_count?: number;
  table?: string;
}
