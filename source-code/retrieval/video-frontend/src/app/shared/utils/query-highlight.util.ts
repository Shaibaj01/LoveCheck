const QUERY_STOP_WORDS = new Set([
  'a', 'an', 'the', 'is', 'are', 'was', 'were', 'be', 'been', 'being',
  'to', 'of', 'in', 'on', 'at', 'by', 'for', 'with', 'from', 'as', 'into',
  'and', 'or', 'but', 'not', 'if', 'then', 'than', 'that', 'this', 'there',
  'it', 'its', 'i', 'you', 'he', 'she', 'we', 'they', 'my', 'your', 'his',
  'next', 'near', 'beside', 'behind', 'around', 'through', 'under', 'over',
  'who', 'what', 'when', 'where', 'which', 'how', 'do', 'does', 'did',
  'has', 'have', 'had', 'can', 'could', 'would', 'should', 'will', 'shall',
  'only', 'just', 'also', 'still', 'even', 'very', 'more', 'most', 'some', 'any',
]);

const QUERY_ACTION_WORDS = new Set([
  'standing', 'stand', 'sitting', 'sit', 'walking', 'walk', 'running', 'run',
  'moving', 'move', 'looking', 'look', 'holding', 'hold', 'wearing', 'wear',
  'talking', 'talk', 'playing', 'play', 'dancing', 'dance', 'jumping', 'jump',
  'lying', 'lie', 'lay', 'eating', 'eat', 'drinking', 'drink', 'driving', 'drive',
]);

export interface SegmentObjectSource {
  vlm_structured?: string | null;
  object_classes?: string | null;
}

function tokenizeQuery(query: string): string[] {
  return (query.toLowerCase().match(/[a-z0-9]+(?:[-'][a-z0-9]+)*/g) ?? []).filter(Boolean);
}

function isSkippableToken(token: string, skip: Set<string>): boolean {
  return skip.has(token) || token.length < 2;
}

function buildContentPhrases(tokens: string[], skip: Set<string>): string[] {
  const phrases: string[] = [];
  let current: string[] = [];
  for (const token of tokens) {
    if (isSkippableToken(token, skip)) {
      if (current.length) {
        phrases.push(current.join(' '));
        current = [];
      }
      continue;
    }
    current.push(token);
  }
  if (current.length) phrases.push(current.join(' '));
  return phrases;
}

export function extractHighlightTerms(query: string): string[] {
  if (!query?.trim()) return [];

  const skip = new Set([...QUERY_STOP_WORDS, ...QUERY_ACTION_WORDS]);
  const phrases = buildContentPhrases(tokenizeQuery(query), skip);

  const terms = new Set<string>();
  for (const phrase of phrases) {
    terms.add(phrase);
    if (phrase.includes(' ')) {
      for (const part of phrase.split(' ')) {
        if (part.includes('-') || part.includes("'")) {
          terms.add(part);
        }
      }
    }
  }

  return Array.from(terms).sort((a, b) => b.length - a.length || a.localeCompare(b));
}

function escapeRegex(value: string): string {
  return value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

function partToPattern(part: string): string {
  if (part.includes('-') || part.includes("'")) {
    return part.split(/[-']/).filter(Boolean).map(escapeRegex).join('[-\\s]?');
  }
  return escapeRegex(part);
}

export function buildTermPattern(term: string): RegExp {
  const parts = term.trim().split(/\s+/).filter(Boolean);
  if (!parts.length) {
    return /$^/;
  }
  const body = parts.map(partToPattern).join('[-\\s]+');
  return new RegExp(`(?<!\\w)(${body})(?!\\w)`, 'gi');
}

export function termInText(term: string, text: string): boolean {
  if (!term || !text) return false;
  return buildTermPattern(term).test(text);
}

export function termMatchesLabel(term: string, label: string): boolean {
  return termInText(term.trim(), label.trim());
}

export function objectMatchesQuery(label: string, terms: string[]): boolean {
  return terms.some(term => termMatchesLabel(term, label));
}

function formatObjectChipLabel(type: string, count: unknown): string {
  const label = type.trim();
  if (!label) return '';
  if (count == null || count === '') return label;
  const numeric = Number(count);
  if (Number.isFinite(numeric) && numeric > 1) {
    return `${Math.trunc(numeric)} ${label}`;
  }
  return label;
}

export function segmentDisplayCaption(segment: {
  dense_caption?: string | null;
  reasoning_content?: string | null;
  vlm_structured?: string | null;
}): string {
  if (segment.vlm_structured?.trim()) {
    try {
      let data: unknown = JSON.parse(segment.vlm_structured);
      if (typeof data === 'string') data = JSON.parse(data);
      const summary = (data as { scene_summary?: string }).scene_summary?.trim();
      if (summary) return summary;
    } catch {
      // ignore malformed structured JSON
    }
  }

  const dense = segment.dense_caption?.trim();
  if (dense) {
    const objectsIdx = dense.indexOf(' | Objects:');
    if (objectsIdx > 0) return dense.slice(0, objectsIdx).trim();
    return dense;
  }

  const reasoning = segment.reasoning_content?.trim();
  if (reasoning) {
    const firstLine = reasoning.split('\n')[0]?.trim();
    if (firstLine) return firstLine;
  }
  return '';
}

export function parseStructuredObjects(segment: SegmentObjectSource): string[] {
  const labels: string[] = [];

  if (segment.vlm_structured?.trim()) {
    try {
      let data: unknown = JSON.parse(segment.vlm_structured);
      if (typeof data === 'string') data = JSON.parse(data);
      if (data && typeof data === 'object' && Array.isArray((data as { objects?: unknown }).objects)) {
        for (const obj of (data as { objects: unknown[] }).objects) {
          if (typeof obj === 'string' && obj.trim()) {
            labels.push(obj.trim());
            continue;
          }
          if (obj && typeof obj === 'object') {
            const typed = obj as { type?: string; count?: unknown };
            const chip = formatObjectChipLabel(typed.type ?? '', typed.count);
            if (chip) labels.push(chip);
          }
        }
      }
    } catch {
      // ignore malformed structured JSON
    }
  }

  if (segment.object_classes?.trim()) {
    segment.object_classes.split(/[,;|]/).forEach(part => {
      const trimmed = part.trim();
      if (trimmed) labels.push(trimmed);
    });
  }

  const seen = new Set<string>();
  return labels.filter(label => {
    const key = label.toLowerCase();
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  });
}

export function highlightQueryTerms(text: string, terms: string[]): string {
  if (!text) return '';
  let escaped = text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');

  for (const term of terms) {
    if (!term || term.length < 2) continue;
    escaped = escaped.replace(buildTermPattern(term), '<span class="query-term-text">$1</span>');
  }
  return escaped;
}

export interface PreviewSegmentLike {
  segment_number: number;
  segment_start_sec: number;
  segment_end_sec: number;
  source: string;
  dense_caption?: string | null;
  reasoning_content?: string | null;
  similarity_score: number;
  query_highlight: boolean;
  is_best_match: boolean;
}

export interface PreviewChunkLike {
  dense_caption?: string | null;
  reasoning_content?: string;
  timeline: PreviewSegmentLike[];
}

/** Prefer query-relevant segment for card preview; fallback to vector best match. */
export function pickPreviewSegment(timeline: PreviewSegmentLike[]): PreviewSegmentLike | null {
  if (!timeline?.length) return null;
  const queryHits = timeline.filter(seg => seg.query_highlight);
  const pool = queryHits.length
    ? queryHits
    : timeline.filter(seg => seg.is_best_match);
  const candidates = pool.length ? pool : timeline;
  return candidates.reduce((best, seg) => {
    if (!best) return seg;
    if (seg.similarity_score > best.similarity_score) return seg;
    if (seg.similarity_score < best.similarity_score) return best;
    return seg.segment_number < best.segment_number ? seg : best;
  });
}

export function previewCaption(chunk: PreviewChunkLike): string {
  const seg = pickPreviewSegment(chunk.timeline);
  if (seg) {
    return segmentDisplayCaption(seg) || (chunk.dense_caption || chunk.reasoning_content || '').trim();
  }
  return (chunk.dense_caption || chunk.reasoning_content || '').trim();
}
