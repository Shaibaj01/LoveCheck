/** Parse ISO timestamps from the API (VastDB rows are UTC; often missing Z). */
export function parseUtcIso(iso: string | null | undefined): Date | null {
  if (!iso) return null;
  const raw = iso.trim();
  if (!raw) return null;
  const hasZone = /[zZ]$/.test(raw) || /[+-]\d{2}:\d{2}$/.test(raw);
  const normalized = hasZone ? raw : `${raw}Z`;
  const date = new Date(normalized);
  return Number.isNaN(date.getTime()) ? null : date;
}

export function formatRelativeTime(iso: string | null | undefined): string {
  const date = parseUtcIso(iso);
  if (!date) return '';
  const sec = Math.max(0, Math.floor((Date.now() - date.getTime()) / 1000));
  if (sec < 60) return 'just now';
  if (sec < 3600) return `${Math.floor(sec / 60)} min ago`;
  if (sec < 86400) return `${Math.floor(sec / 3600)} hr ago`;
  return date.toLocaleString(undefined, {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

export function formatAbsoluteTime(iso: string | null | undefined): string {
  const date = parseUtcIso(iso);
  if (!date) return iso || '—';
  return date.toLocaleString();
}
