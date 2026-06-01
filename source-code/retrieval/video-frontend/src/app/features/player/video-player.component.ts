import {
  Component,
  Inject,
  OnInit,
  ViewChild,
  ElementRef,
  inject,
  signal,
  computed,
} from '@angular/core';
import { CommonModule } from '@angular/common';
import { MAT_DIALOG_DATA, MatDialogModule, MatDialogRef } from '@angular/material/dialog';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { MatTooltipModule } from '@angular/material/tooltip';
import { DomSanitizer, SafeHtml, SafeResourceUrl } from '@angular/platform-browser';
import { ChunkSearchResult, TimelineSegment, VideoSearchResult } from '../../shared/models/video.model';
import { VideoService } from '../../shared/services/video.service';
import {
  extractHighlightTerms,
  highlightQueryTerms,
  objectMatchesQuery,
  parseStructuredObjects,
  segmentDisplayCaption,
} from '../../shared/utils/query-highlight.util';

export interface VideoPlayerData {
  chunk?: ChunkSearchResult;
  video?: VideoSearchResult;
  query?: string;
  initialSeekSec?: number;
}

@Component({
  selector: 'app-video-player',
  standalone: true,
  imports: [
    CommonModule,
    MatDialogModule,
    MatButtonModule,
    MatIconModule,
    MatProgressSpinnerModule,
    MatTooltipModule,
  ],
  template: `
    <div class="video-player-container">
      <div class="player-header">
        <div class="header-info">
          <mat-icon class="video-icon">play_circle</mat-icon>
          <div>
            <h2>{{ title() }}</h2>
            @if (chunk()) {
              <p class="subtitle">Full chunk · {{ formatTime(chunk()!.chunk_duration_sec) }} · {{ chunk()!.total_segments }} segments</p>
            }
          </div>
        </div>
        <button mat-icon-button class="close-btn" (click)="close()" matTooltip="Close">
          <mat-icon>close</mat-icon>
        </button>
      </div>

      @if (chunk()) {
        <div class="jump-bar">
          <button mat-stroked-button class="jump-btn" (click)="seekToBestMatch()">
            <mat-icon>my_location</mat-icon>
            Jump to moment · {{ formatTime(chunk()!.best_match_start_sec) }}
          </button>
          <span class="jump-query">Searching: "{{ chunk()!.query }}"</span>
        </div>
      }

      <div class="video-section">
        @if (loading()) {
          <div class="loading-overlay">
            <mat-spinner diameter="48"></mat-spinner>
            <p>Loading video...</p>
          </div>
        }

        @if (streamUrl() && !error()) {
          <video
            #videoPlayer
            [src]="streamUrl()"
            controls
            playsinline
            [muted]="true"
            (loadedmetadata)="onVideoLoaded()"
            (timeupdate)="onTimeUpdate()"
            (error)="onVideoError($event)"
            class="video-player">
          </video>
        }

        @if (error()) {
          <div class="error-state">
            <mat-icon>error_outline</mat-icon>
            <p>{{ error() }}</p>
            <button mat-raised-button color="primary" (click)="loadVideo()">
              <mat-icon>refresh</mat-icon>
              Retry
            </button>
          </div>
        }
      </div>

      @if (chunk()) {
        <div class="moment-timeline">
          <div class="timeline-header">
            <mat-icon>timeline</mat-icon>
            <span>Jump to moment</span>
            <span class="playhead">{{ formatTime(currentTime()) }} / {{ formatTime(chunk()!.chunk_duration_sec) }}</span>
          </div>
          <div class="timeline-track">
            @for (seg of chunk()!.timeline; track seg.source) {
              <button
                type="button"
                class="timeline-seg"
                [style.flex]="segmentFlex(seg)"
                [class.active]="activeSegmentNumber() === seg.segment_number"
                [class.search-match]="seg.is_search_match"
                [class.query-hit]="seg.query_highlight"
                [class.best-match]="seg.is_best_match"
                (click)="seekToSegment(seg)"
                [matTooltip]="segmentTooltip(seg)">
                <span class="seg-num">{{ seg.segment_number }}</span>
              </button>
            }
          </div>
        </div>

        <div class="segments-panel">
          @for (seg of chunk()!.timeline; track seg.source) {
            <button
              type="button"
              class="segment-row"
              [class.active]="activeSegmentNumber() === seg.segment_number"
              [class.highlight]="seg.query_highlight"
              (click)="seekToSegment(seg)">
              <div class="seg-time">
                <span class="seg-range">{{ formatTime(seg.segment_start_sec) }}–{{ formatTime(seg.segment_end_sec) }}</span>
                @if (seg.is_best_match) {
                  <span class="best-pill">Best match</span>
                } @else if (seg.query_highlight) {
                  <span class="hit-pill">Query hit</span>
                }
              </div>
              <p class="seg-caption" [innerHTML]="highlightHtml(segmentDisplayCaption(seg))"></p>
              @if (segmentObjects(seg).length) {
                <div class="seg-objects">
                  @for (obj of segmentObjects(seg); track obj) {
                    <span class="obj-chip" [class.hit]="isQueryTerm(obj)">{{ obj }}</span>
                  }
                </div>
              }
              @if (seg.is_search_match && seg.similarity_score > 0) {
                <span class="seg-score">{{ (seg.similarity_score * 100).toFixed(0) }}% relevance</span>
              }
            </button>
          }
        </div>
      } @else if (legacyVideo()) {
        <div class="segment-nav-bar">
          <button mat-icon-button (click)="previousSegment()" [disabled]="isFirstSegment()">
            <mat-icon>skip_previous</mat-icon>
          </button>
          <span>Segment {{ legacyVideo()!.segment_number }}/{{ legacyVideo()!.total_segments }}</span>
          <button mat-icon-button (click)="nextSegment()" [disabled]="isLastSegment()">
            <mat-icon>skip_next</mat-icon>
          </button>
        </div>
        <div class="info-section">
          <div class="reasoning-card">
            <p>{{ legacyVideo()!.reasoning_content }}</p>
          </div>
        </div>
      }
    </div>
  `,
  styles: [`
    .video-player-container {
      display: flex;
      flex-direction: column;
      height: 100%;
      max-height: 92vh;
      background: var(--bg-primary);
      color: var(--text-primary);
      overflow: hidden;
    }

    .player-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      padding: 0.75rem 1.25rem;
      background: var(--bg-card);
      border-bottom: 1px solid var(--border-color);

      h2 {
        margin: 0;
        font-size: 1rem;
        font-weight: 600;
        max-width: 520px;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
      }

      .subtitle {
        margin: 0.15rem 0 0;
        font-size: 0.78rem;
        color: var(--text-muted);
      }

      .video-icon { color: var(--accent-primary); }
    }

    .jump-bar {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 1rem;
      padding: 0.55rem 1rem;
      background: rgba(34, 197, 94, 0.08);
      border-bottom: 1px solid rgba(34, 197, 94, 0.22);
      flex-wrap: wrap;
    }

    .jump-btn {
      border-color: rgba(34, 197, 94, 0.55) !important;
      color: #22c55e !important;
      font-weight: 600;
    }

    .jump-query {
      font-size: 0.78rem;
      color: var(--text-secondary);
    }

    .video-section {
      position: relative;
      background: #000;
      flex-shrink: 0;
      max-height: 42vh;

      .video-player {
        width: 100%;
        max-height: 42vh;
        object-fit: contain;
        display: block;
      }
    }

    .loading-overlay, .error-state {
      min-height: 220px;
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      gap: 0.75rem;
      padding: 1.5rem;
    }

    .moment-timeline {
      padding: 0.75rem 1rem 0.5rem;
      border-bottom: 1px solid var(--border-color);
      background: var(--bg-card);
    }

    .timeline-header {
      display: flex;
      align-items: center;
      gap: 0.4rem;
      font-size: 0.78rem;
      text-transform: uppercase;
      letter-spacing: 0.04em;
      color: var(--text-muted);
      margin-bottom: 0.45rem;

      .playhead {
        margin-left: auto;
        font-family: monospace;
        text-transform: none;
        letter-spacing: 0;
      }
    }

    .timeline-track {
      display: flex;
      gap: 3px;
      height: 36px;
      border-radius: 8px;
      overflow: hidden;
      border: 1px solid var(--border-color);
    }

    .timeline-seg {
      position: relative;
      border: none;
      padding: 0;
      min-width: 10px;
      background: rgba(148, 163, 184, 0.22);
      cursor: pointer;
      transition: transform 0.15s, box-shadow 0.15s;

      &:hover { transform: scaleY(1.06); }

      &.search-match { background: rgba(59, 130, 246, 0.4); }
      &.query-hit { background: rgba(34, 197, 94, 0.5); }
      &.best-match {
        background: linear-gradient(180deg, #22c55e, #16a34a);
      }
      &.active {
        box-shadow: inset 0 0 0 2px #fff, 0 0 0 2px #22c55e;
        z-index: 1;
      }

      .seg-num {
        position: absolute;
        inset: 0;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 0.68rem;
        font-weight: 700;
        color: rgba(255, 255, 255, 0.9);
      }
    }

    .segments-panel {
      flex: 1;
      overflow-y: auto;
      padding: 0.75rem 1rem 1rem;
      display: flex;
      flex-direction: column;
      gap: 0.55rem;
    }

    .segment-row {
      text-align: left;
      border: 1px solid var(--border-color);
      border-radius: 12px;
      padding: 0.65rem 0.75rem;
      background: var(--bg-card);
      cursor: pointer;
      transition: border-color 0.2s, background 0.2s;

      &:hover { background: var(--bg-card-hover); }
      &.active {
        border-color: rgba(34, 197, 94, 0.65);
        box-shadow: 0 0 0 1px rgba(34, 197, 94, 0.25);
      }
      &.highlight {
        border-color: rgba(34, 197, 94, 0.45);
        background: rgba(34, 197, 94, 0.06);
      }
    }

    .seg-time {
      display: flex;
      align-items: center;
      gap: 0.5rem;
      margin-bottom: 0.35rem;
    }

    .seg-range {
      font-size: 0.78rem;
      font-weight: 700;
      color: var(--accent-primary);
      font-family: monospace;
    }

    .best-pill, .hit-pill {
      font-size: 0.65rem;
      padding: 0.1rem 0.4rem;
      border-radius: 999px;
      font-weight: 700;
      text-transform: uppercase;
    }

    .best-pill {
      background: rgba(34, 197, 94, 0.2);
      color: #22c55e;
    }

    .hit-pill {
      background: rgba(34, 197, 94, 0.12);
      color: #86efac;
    }

    .seg-caption {
      margin: 0 0 0.4rem;
      font-size: 0.85rem;
      line-height: 1.5;
      color: var(--text-secondary);

      ::ng-deep .query-term-text {
        color: #22c55e;
        font-weight: 600;
      }
    }

    .seg-objects {
      display: flex;
      flex-wrap: wrap;
      gap: 0.3rem;
      margin-bottom: 0.25rem;
    }

    .obj-chip {
      font-size: 0.68rem;
      padding: 0.1rem 0.4rem;
      border-radius: 999px;
      background: var(--bg-secondary);
      border: 1px solid var(--border-color);
      color: var(--text-muted);

      &.hit {
        color: #22c55e;
        font-weight: 600;
      }
    }

    .seg-score {
      font-size: 0.72rem;
      color: #73c8fd;
    }

    .segment-nav-bar, .info-section, .reasoning-card {
      padding: 0.75rem 1rem;
    }
  `],
})
export class VideoPlayerComponent implements OnInit {
  private videoService = inject(VideoService);
  private sanitizer = inject(DomSanitizer);
  private dialogRef = inject(MatDialogRef<VideoPlayerComponent>);

  @ViewChild('videoPlayer') videoPlayer?: ElementRef<HTMLVideoElement>;

  loading = signal(true);
  error = signal<string | null>(null);
  streamUrl = signal<SafeResourceUrl | null>(null);
  currentTime = signal(0);
  chunk = signal<ChunkSearchResult | null>(null);
  legacyVideo = signal<VideoSearchResult | null>(null);
  queryTerms = signal<string[]>([]);
  pendingSeekSec: number | null = null;

  title = computed(() => this.chunk()?.filename ?? this.legacyVideo()?.filename ?? 'Video');

  activeSegmentNumber = computed(() => {
    const c = this.chunk();
    const t = this.currentTime();
    if (!c) return 0;
    for (const seg of c.timeline) {
      if (t >= seg.segment_start_sec && t < seg.segment_end_sec) {
        return seg.segment_number;
      }
    }
    const last = c.timeline[c.timeline.length - 1];
    if (last && t >= last.segment_start_sec) return last.segment_number;
    return c.best_segment_number;
  });

  constructor(@Inject(MAT_DIALOG_DATA) public data: VideoPlayerData) {}

  ngOnInit() {
    if (this.data.chunk) {
      this.chunk.set(this.data.chunk);
      this.queryTerms.set(extractHighlightTerms(this.data.query ?? this.data.chunk.query));
      this.pendingSeekSec =
        this.data.initialSeekSec ??
        this.data.chunk.best_match_start_sec ??
        0;
    } else if (this.data.video) {
      this.legacyVideo.set(this.data.video);
    }
    this.loadVideo();
  }

  loadVideo() {
    this.loading.set(true);
    this.error.set(null);

    try {
      const token = localStorage.getItem('video_lab_token');
      if (!token) throw new Error('No authentication token found');

      const source = this.chunk()?.original_video ?? this.legacyVideo()?.source ?? '';
      const streamUrl = this.videoService.getStreamUrl(source, token);
      this.streamUrl.set(this.sanitizer.bypassSecurityTrustResourceUrl(streamUrl));
    } catch (err: any) {
      this.error.set(err.message ?? 'Failed to load video');
      this.loading.set(false);
    }
  }

  onVideoLoaded() {
    this.loading.set(false);
    if (this.pendingSeekSec != null && this.videoPlayer?.nativeElement) {
      this.videoPlayer.nativeElement.currentTime = this.pendingSeekSec;
      this.pendingSeekSec = null;
    }
  }

  onTimeUpdate() {
    const el = this.videoPlayer?.nativeElement;
    if (el) this.currentTime.set(el.currentTime);
  }

  onVideoError(event?: Event) {
    console.error('[VIDEO PLAYER]', event);
    this.error.set('Failed to load video. Please try again.');
    this.loading.set(false);
  }

  seekToBestMatch() {
    const c = this.chunk();
    if (!c) return;
    this.seekTo(c.best_match_start_sec + 0.05);
  }

  seekToSegment(seg: TimelineSegment) {
    this.seekTo(seg.segment_start_sec + 0.05);
  }

  seekTo(sec: number) {
    const el = this.videoPlayer?.nativeElement;
    if (!el) return;
    el.currentTime = sec;
    el.play().catch(() => undefined);
  }

  segmentFlex(seg: TimelineSegment): string {
    const len = Math.max(seg.segment_end_sec - seg.segment_start_sec, 0.5);
    return `${len} 1 0`;
  }

  formatTime(seconds: number): string {
    if (seconds == null || Number.isNaN(seconds)) return '0:00';
    const total = Math.floor(seconds);
    const mins = Math.floor(total / 60);
    const secs = total % 60;
    return `${mins}:${secs.toString().padStart(2, '0')}`;
  }

  segmentTooltip(seg: TimelineSegment): string {
    return `#${seg.segment_number} ${this.formatTime(seg.segment_start_sec)}–${this.formatTime(seg.segment_end_sec)}`;
  }

  segmentObjects(seg: TimelineSegment): string[] {
    return parseStructuredObjects(seg).slice(0, 6);
  }

  readonly segmentDisplayCaption = segmentDisplayCaption;

  isQueryTerm(label: string): boolean {
    return objectMatchesQuery(label, this.queryTerms());
  }

  highlightHtml(text: string): SafeHtml {
    if (!text) return '';
    const html = highlightQueryTerms(text, this.queryTerms());
    return this.sanitizer.bypassSecurityTrustHtml(html);
  }

  isFirstSegment(): boolean {
    return (this.legacyVideo()?.segment_number ?? 1) === 1;
  }

  isLastSegment(): boolean {
    const v = this.legacyVideo();
    return !!v && v.segment_number === v.total_segments;
  }

  async previousSegment() {
    const v = this.legacyVideo();
    if (!v || this.isFirstSegment()) return;
    const n = v.segment_number - 1;
    const newSource = v.source.replace(
      `_segment_${String(v.segment_number).padStart(3, '0')}_of_`,
      `_segment_${String(n).padStart(3, '0')}_of_`
    );
    try {
      const metadata = await this.videoService.getVideoMetadata(newSource).toPromise();
      this.legacyVideo.set({ ...v, ...metadata, source: newSource, segment_number: n });
    } catch {
      this.legacyVideo.set({ ...v, source: newSource, segment_number: n });
    }
    this.loadVideo();
  }

  async nextSegment() {
    const v = this.legacyVideo();
    if (!v || this.isLastSegment()) return;
    const n = v.segment_number + 1;
    const newSource = v.source.replace(
      `_segment_${String(v.segment_number).padStart(3, '0')}_of_`,
      `_segment_${String(n).padStart(3, '0')}_of_`
    );
    try {
      const metadata = await this.videoService.getVideoMetadata(newSource).toPromise();
      this.legacyVideo.set({ ...v, ...metadata, source: newSource, segment_number: n });
    } catch {
      this.legacyVideo.set({ ...v, source: newSource, segment_number: n });
    }
    this.loadVideo();
  }

  close() {
    this.dialogRef.close();
  }
}
