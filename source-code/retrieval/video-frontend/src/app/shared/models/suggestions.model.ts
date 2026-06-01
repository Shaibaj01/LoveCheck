export interface KeyEventSuggestion {
  query_text: string;
  label: string;
  original_video: string;
  filename: string;
  segment_start_sec: number;
  segment_end_sec: number;
}

export interface SuggestionsResponse {
  batch_id: string | null;
  generated_at: string | null;
  search_prompts: string[];
  key_events: KeyEventSuggestion[];
  table?: string;
}
