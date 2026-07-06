import { ChunkSearchResult } from '../models/video.model';

export function explorePlayLabel(
  chunk: Pick<ChunkSearchResult, 'chunk_index' | 'stream_chunk_total'>,
): string {
  const idx = chunk.chunk_index;
  if (idx != null && idx >= 0) {
    const n = idx + 1;
    const total = chunk.stream_chunk_total;
    if (total != null && total > 0) {
      return `Play chunk ${n}/${total}`;
    }
    return `Play chunk ${n}`;
  }
  return 'Play from start';
}

export function relativeBarWidth(value: number, values: number[], minPct = 4): number {
  const max = Math.max(...values, 1);
  return Math.max(minPct, (value / max) * 100);
}
