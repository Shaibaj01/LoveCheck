export interface MetadataOption {
  value: string;
  label: string;
}

export interface FilterableMetadataField {
  key: string;
  label: string;
}

export interface IngestMetadataConfig {
  custom_prompt_max_length: number;
  filterable_fields: FilterableMetadataField[];
  capture_types: MetadataOption[];
  capture_type_default_label: string;
  analysis_scenarios: MetadataOption[];
  analysis_scenario_default_label: string;
  labels: Record<string, string>;
  placeholders: Record<string, string>;
}

export type IngestMetadataFieldSet = 'all' | 'location' | 'analysis';
