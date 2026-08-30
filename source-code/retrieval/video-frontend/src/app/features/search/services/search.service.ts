import { Injectable, inject, signal } from '@angular/core';
import { VideoService } from '../../../shared/services/video.service';
import { SearchRequest, VideoSearchResult, ChunkSearchResult, LLMSynthesis } from '../../../shared/models/video.model';

export type SearchAnimationPhase =
  | 'idle'
  | 'embedding'
  | 'searching'
  | 'filtering'
  | 'synthesizing'
  | 'complete';

export interface SearchState {
  loading: boolean;
  results: VideoSearchResult[];
  chunkResults: ChunkSearchResult[];
  query: string;
  error: string | null;
  embeddingTimeMs: number;
  searchTimeMs: number;
  llmTimeMs: number;
  permissionFiltered: number;
  llmSynthesis: LLMSynthesis | null;
  expectSynthesis: boolean;
  animationPhase: SearchAnimationPhase;
  sqlQuery: string | null;
}

@Injectable({
  providedIn: 'root'
})
export class SearchService {
  private videoService = inject(VideoService);
  private phaseTimer: ReturnType<typeof setInterval> | null = null;

  state = signal<SearchState>({
    loading: false,
    results: [],
    chunkResults: [],
    query: '',
    error: null,
    embeddingTimeMs: 0,
    searchTimeMs: 0,
    llmTimeMs: 0,
    permissionFiltered: 0,
    llmSynthesis: null,
    expectSynthesis: false,
    animationPhase: 'idle',
    sqlQuery: null
  });

  async search(request: SearchRequest) {
    const expectSynthesis = (request.llm_top_n ?? 3) > 0;
    this.stopPhaseProgression();

    this.state.update(s => ({
      ...s,
      loading: true,
      error: null,
      query: request.query,
      llmSynthesis: null,
      expectSynthesis,
      animationPhase: 'embedding',
      embeddingTimeMs: 0,
      searchTimeMs: 0,
      llmTimeMs: 0,
    }));

    this.startPhaseProgression(expectSynthesis);

    try {
      const response = await this.videoService.search(request).toPromise();
      this.stopPhaseProgression();

      if (response) {
        const hasSynthesis = !!response.llm_synthesis;
        if (hasSynthesis) {
          this.state.update(s => ({ ...s, animationPhase: 'synthesizing' }));
          await this.delay(150);
        }

        this.state.update(s => ({
          ...s,
          loading: false,
          results: response.results,
          chunkResults: response.chunk_results ?? [],
          embeddingTimeMs: response.embedding_time_ms,
          searchTimeMs: response.search_time_ms,
          llmTimeMs: response.llm_synthesis?.processing_time
            ? response.llm_synthesis.processing_time * 1000
            : 0,
          permissionFiltered: response.permission_filtered,
          llmSynthesis: response.llm_synthesis || null,
          expectSynthesis: hasSynthesis,
          animationPhase: 'complete',
          sqlQuery: response.sql_query || null
        }));
      }
    } catch (error: any) {
      this.stopPhaseProgression();
      this.state.update(s => ({
        ...s,
        loading: false,
        error: this.getErrorMessage(error),
        expectSynthesis: false,
        animationPhase: 'idle'
      }));
    }
  }

  clearResults() {
    this.stopPhaseProgression();
    this.state.update(s => ({
      ...s,
      results: [],
      chunkResults: [],
      query: '',
      error: null,
      embeddingTimeMs: 0,
      searchTimeMs: 0,
      llmTimeMs: 0,
      llmSynthesis: null,
      expectSynthesis: false,
      animationPhase: 'idle',
      sqlQuery: null
    }));
  }

  closeAnimation() {
    this.state.update(s => ({
      ...s,
      animationPhase: 'idle'
    }));
  }

  /** Advance UI phases while the single search HTTP request is in flight. */
  private startPhaseProgression(expectSynthesis: boolean) {
    const schedule: Array<{ atMs: number; phase: SearchAnimationPhase }> = [
      { atMs: 0, phase: 'embedding' },
      { atMs: 700, phase: 'searching' },
      { atMs: 1400, phase: 'filtering' },
    ];
    if (expectSynthesis) {
      schedule.push({ atMs: 1800, phase: 'synthesizing' });
    }

    const started = Date.now();
    this.phaseTimer = setInterval(() => {
      if (!this.state().loading) {
        this.stopPhaseProgression();
        return;
      }
      const elapsed = Date.now() - started;
      let phase: SearchAnimationPhase = schedule[0].phase;
      for (const step of schedule) {
        if (elapsed >= step.atMs) {
          phase = step.phase;
        }
      }
      if (this.state().animationPhase !== phase) {
        this.state.update(s => ({ ...s, animationPhase: phase }));
      }
    }, 80);
  }

  private stopPhaseProgression() {
    if (this.phaseTimer !== null) {
      clearInterval(this.phaseTimer);
      this.phaseTimer = null;
    }
  }

  private delay(ms: number): Promise<void> {
    return new Promise(resolve => setTimeout(resolve, ms));
  }

  private getErrorMessage(error: any): string {
    const detail = error?.error?.detail;
    if (typeof detail === 'string' && detail.trim()) {
      return detail;
    }

    if (Array.isArray(detail)) {
      const parts = detail
        .map((d: any) => {
          if (!d || typeof d !== 'object') {
            return '';
          }
          const msg = typeof d.msg === 'string' ? d.msg : '';
          const loc = Array.isArray(d.loc) ? d.loc.join('.') : '';
          return msg ? (loc ? `${loc}: ${msg}` : msg) : '';
        })
        .filter((p: string) => !!p);
      if (parts.length > 0) {
        return parts.join(' | ');
      }
    }

    if (typeof error?.error === 'string' && error.error.trim()) {
      return error.error;
    }
    if (typeof error?.message === 'string' && error.message.trim()) {
      return error.message;
    }

    return 'Search failed. Please try again.';
  }
}
