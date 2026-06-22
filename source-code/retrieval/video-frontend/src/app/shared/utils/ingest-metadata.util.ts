/** Parse comma-separated form values (tags, allowed users). */
export function parseCommaList(value: string | null | undefined): string[] {
  if (!value?.trim()) {
    return [];
  }
  return value.split(',').map((part) => part.trim()).filter(Boolean);
}

/** Map ingest metadata form values to API payload fields. */
export function pickIngestMetadataPayload(formValue: {
  camera_id?: string | null;
  capture_type?: string | null;
  location?: string | null;
  scenario?: string | null;
  useCustomPrompt?: boolean | null;
  custom_prompt?: string | null;
}): {
  camera_id?: string;
  capture_type?: string;
  location?: string;
  scenario?: string;
  custom_prompt?: string;
} {
  const scenario = formValue.useCustomPrompt ? '' : (formValue.scenario || '');
  return {
    camera_id: formValue.camera_id?.trim() || undefined,
    capture_type: formValue.capture_type?.trim() || undefined,
    location: formValue.location?.trim() || undefined,
    scenario: scenario || undefined,
    custom_prompt: formValue.useCustomPrompt
      ? formValue.custom_prompt?.trim() || undefined
      : undefined,
  };
}
