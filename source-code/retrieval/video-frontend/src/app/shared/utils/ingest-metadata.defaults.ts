import { IngestMetadataConfig } from '../models/ingest-metadata.model';

/**
 * Offline fallback — keep aligned with source-code/shared/ingest_metadata.py
 * Used when GET /metadata/ingest-config is unavailable.
 */
export const DEFAULT_INGEST_METADATA_CONFIG: IngestMetadataConfig = {
  custom_prompt_max_length: 800,
  filterable_fields: [
    { key: 'camera_id', label: 'Camera ID' },
    { key: 'capture_type', label: 'Capture Type' },
    { key: 'location', label: 'Location' },
  ],
  capture_types: [
    { value: 'traffic', label: 'Traffic' },
    { value: 'streets', label: 'Streets' },
    { value: 'crowds', label: 'Crowds' },
    { value: 'malls', label: 'Malls' },
    { value: 'general', label: 'General' },
    { value: 'sports', label: 'Sports' },
    { value: 'robotics', label: 'Robotics' },
    { value: 'warehouse', label: 'Warehouse' },
    { value: 'retail', label: 'Retail' },
  ],
  capture_type_default_label: '-- Select Type --',
  analysis_scenarios: [
    { value: 'surveillance', label: 'Incident & Safety Detection' },
    { value: 'traffic', label: 'Vehicle & Pedestrian Monitoring' },
    { value: 'live_driving', label: 'Live Driving & Road Safety' },
    { value: 'nhl', label: 'Hockey Game Analysis' },
    { value: 'sports', label: 'General Sports Analysis' },
    { value: 'retail', label: 'Retail Store Monitoring' },
    { value: 'warehouse', label: 'Warehouse Safety & Operations' },
    { value: 'nyc_control', label: 'NYC Traffic & Public Safety' },
    { value: 'nyc_safety_surveillance', label: 'NYC Street Safety Surveillance' },
    { value: 'egocentric', label: 'First-Person Activity Analysis' },
    { value: 'general', label: 'General Video Analysis' },
  ],
  analysis_scenario_default_label: '-- Use Default (from settings) --',
  labels: {
    camera_id: 'Camera ID',
    capture_type: 'Capture Type',
    location: 'Location',
    use_custom_prompt: 'Use custom prompt (overrides scenario)',
    metadata_section_title: 'Stream Metadata (Optional)',
    metadata_section_description:
      'These fields will be stored with each video segment for filtering and search',
  },
  placeholders: {
    camera_id: 'e.g., CAM-001, manhattan-cam-1',
    location: 'e.g., Midtown, Downtown, Times Square',
    tags: 'demo, outdoor, test',
    allowed_users: 'john.doe, jane.smith',
    custom_prompt: 'Enter your custom reasoning prompt for the AI model...',
  },
};

export function isValidIngestMetadataConfig(value: unknown): value is IngestMetadataConfig {
  if (!value || typeof value !== 'object') {
    return false;
  }
  const data = value as IngestMetadataConfig;
  return (
    typeof data.custom_prompt_max_length === 'number' &&
    Array.isArray(data.filterable_fields) &&
    Array.isArray(data.capture_types) &&
    Array.isArray(data.analysis_scenarios) &&
    typeof data.capture_type_default_label === 'string' &&
    typeof data.analysis_scenario_default_label === 'string' &&
    !!data.labels &&
    typeof data.labels === 'object' &&
    !!data.placeholders &&
    typeof data.placeholders === 'object'
  );
}
