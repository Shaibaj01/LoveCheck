export interface KeyEventSuggestion {
  query_text: string;
  label: string;
  original_video: string;
  filename: string;
    segment_start_sec: number;
  segment_end_sec: number;
  upload_timestamp?: string | null;
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
  prompts_table_available?: boolean;
  table_message?: string | null;
}
