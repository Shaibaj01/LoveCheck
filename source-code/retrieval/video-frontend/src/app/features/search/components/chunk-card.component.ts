import {
  Component,
  EventEmitter,
  Input,
  Output,
  ViewChild,
  ElementRef,
  inject,
  OnChanges,
  SimpleChanges,
} from '@angular/core';
import { CommonModule } from '@angular/common';
import { MatCardModule } from '@angular/material/card';
import { MatIconModule } from '@angular/material/icon';
import { MatChipsModule } from '@angular/material/chips';
import { MatTooltipModule } from '@angular/material/tooltip';
import { MatButtonModule } from '@angular/material/button';
import { DomSanitizer, SafeHtml } from '@angular/platform-browser';
import { ChunkSearchResult } from '../../../shared/models/video.model';
import { VideoService } from '../../../shared/services/video.service';
import {
  extractHighlightTerms,
  highlightQueryTerms,
  objectMatchesQuery,
  parseStructuredObjects,
  previewCaption,
} from '../../../shared/utils/query-highlight.util';

@Component({
  selector: 'app-chunk-card',
  standalone: true,
  imports: [
    CommonModule,
    MatCardModule,
    MatIconModule,
    MatChipsModule,
    MatTooltipModule,
    MatButtonModule,
  ],
  template: `
        <mat-card class="chunk-card" (click)="onOpen()"
              (mouseenter)="onHoverStart()"
              (mouseleave)="onHoverEnd()">
      <div class="video-preview-container">
        <video
          #videoElement
          [src]="previewUrl"
          class="video-preview"
          [muted]="true"
          [loop]="true"
          playsinline
          preload="metadata"
          (loadeddata)="onVideoLoaded()">
        </video>
        <div class="play-overlay" [class.hidden]="isPlaying">
          <mat-icon>play_circle_filled</mat-icon>
        </div>
        <div class="jump-badge">
          <mat-icon>my_location</mat-icon>
          Jump to {{ formatTime(chunk.best_match_start_sec) }}
        </div>
        <div class="score-badge">
          {{ (chunk.similarity_score * 100).toFixed(0) }}% match
        </div>
      </div>

      <mat-card-content>
        <div class="title-row">
          <h3 class="chunk-title">{{ chunk.filename }}</h3>
          <span class="duration-chip">{{ formatTime(chunk.chunk_duration_sec) }}</span>
        </div>

        <p class="match-line">
          Best moment
          <strong>{{ formatTime(chunk.best_match_start_sec) }}–{{ formatTime(chunk.best_match_end_sec) }}</strong>
          · segment {{ chunk.best_segment_number }}/{{ chunk.total_segments }}
          @if (chunk.matched_segment_count > 1) {
            <span class="multi-hit">· {{ chunk.matched_segment_count }} hits</span>
          }
        </p>

        <div class="timeline-section">
          <div class="timeline-label">
            <mat-icon>timeline</mat-icon>
            Chunk timeline
          </div>
          <div class="timeline-track">
            @for (seg of chunk.timeline; track seg.segment_number) {
              <button
                type="button"
                class="timeline-seg"
                [style.flex]="segmentFlex(seg)"
                [class.search-match]="seg.is_search_match"
                [class.query-hit]="seg.query_highlight"
                [class.best-match]="seg.is_best_match"
                (click)="onSegmentClick($event, seg.segment_start_sec)"
                [matTooltip]="segmentTooltip(seg)"
                matTooltipShowDelay="400">
                @if (seg.is_best_match) {
                  <mat-icon class="seg-pin">place</mat-icon>
                }
              </button>
            }
          </div>
          <div class="timeline-legend">
            <span class="legend-item"><span class="dot best"></span> Best match</span>
            <span class="legend-item"><span class="dot hit"></span> Query / match</span>
          </div>
        </div>

        <div class="reasoning-content">
          <mat-icon class="reasoning-icon">psychology</mat-icon>
          <p [innerHTML]="highlightHtml(cardCaption())"></p>
        </div>

        <div class="object-tags">
          @for (obj of objectTags(); track obj) {
            <span class="object-chip" [class.highlight]="isQueryTerm(obj)">{{ obj }}</span>
          }
        </div>

        <div class="video-metadata">
          @if (chunk.camera_id?.trim()) {
            <span class="metadata-item"><mat-icon>videocam</mat-icon>{{ chunk.camera_id }}</span>
          }
          @if (chunk.location?.trim()) {
            <span class="metadata-item"><mat-icon>location_on</mat-icon>{{ chunk.location }}</span>
          }
          <span class="metadata-item">
            <mat-icon>{{ chunk.is_public ? 'public' : 'lock' }}</mat-icon>
            {{ chunk.is_public ? 'Public' : 'Private' }}
          </span>
        </div>

        <button mat-stroked-button class="open-btn" (click)="onOpen($event)">
          <mat-icon>play_arrow</mat-icon>
          Open with timeline
        </button>
      </mat-card-content>
    </mat-card>
  `,
  styles: [`
    .chunk-card {
      background: var(--bg-card);
      border: 1px solid var(--border-color);
      border-radius: 16px;
      cursor: pointer;
      transition: all 0.3s ease;
      overflow: hidden;

      &:hover {
        transform: translateY(-4px);
        box-shadow: var(--shadow-hover);
        border-color: rgba(34, 197, 94, 0.45);
      }
    }

    .video-preview-container {
      position: relative;
      height: 200px;
      background: #000;
      overflow: hidden;
    }

    .video-preview {
      width: 100%;
      height: 100%;
      object-fit: cover;
    }

    .play-overlay {
      position: absolute;
      inset: 0;
      display: flex;
      align-items: center;
      justify-content: center;
      background: rgba(0, 0, 0, 0.35);
      pointer-events: none;
      transition: opacity 0.25s;

      &.hidden { opacity: 0; }

      mat-icon {
        font-size: 3.5rem;
        width: 3.5rem;
        height: 3.5rem;
        color: #fff;
      }
    }

    .jump-badge {
      position: absolute;
      left: 10px;
      bottom: 10px;
      display: inline-flex;
      align-items: center;
      gap: 0.35rem;
      padding: 0.35rem 0.65rem;
      border-radius: 999px;
      background: rgba(34, 197, 94, 0.92);
      color: #052e16;
      font-size: 0.78rem;
      font-weight: 700;
      box-shadow: 0 2px 12px rgba(34, 197, 94, 0.45);

      mat-icon {
        font-size: 1rem;
        width: 1rem;
        height: 1rem;
      }
    }

    .score-badge {
      position: absolute;
      top: 10px;
      right: 10px;
      padding: 0.3rem 0.55rem;
      border-radius: 8px;
      background: rgba(0, 0, 0, 0.72);
      color: #73c8fd;
      font-size: 0.75rem;
      font-weight: 600;
      border: 1px solid rgba(115, 200, 253, 0.35);
    }

    .title-row {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 0.75rem;
      margin-bottom: 0.35rem;
    }

    .chunk-title {
      margin: 0;
      font-size: 1rem;
      font-weight: 600;
      color: var(--text-primary);
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
      flex: 1;
    }

    .duration-chip {
      font-size: 0.75rem;
      color: var(--text-secondary);
      background: var(--bg-secondary);
      border: 1px solid var(--border-color);
      border-radius: 999px;
      padding: 0.15rem 0.55rem;
      flex-shrink: 0;
    }

    .match-line {
      margin: 0 0 0.75rem;
      font-size: 0.82rem;
      color: var(--text-secondary);

      strong { color: #22c55e; }
      .multi-hit { color: var(--text-muted); }
    }

    .timeline-section {
      margin-bottom: 0.85rem;
    }

    .timeline-label {
      display: flex;
      align-items: center;
      gap: 0.35rem;
      font-size: 0.72rem;
      text-transform: uppercase;
      letter-spacing: 0.04em;
      color: var(--text-muted);
      margin-bottom: 0.4rem;

      mat-icon {
        font-size: 0.95rem;
        width: 0.95rem;
        height: 0.95rem;
      }
    }

    .timeline-track {
      display: flex;
      gap: 3px;
      height: 28px;
      border-radius: 8px;
      overflow: hidden;
      background: var(--bg-secondary);
      border: 1px solid var(--border-color);
    }

    .timeline-seg {
      position: relative;
      border: none;
      padding: 0;
      min-width: 8px;
      background: rgba(148, 163, 184, 0.25);
      cursor: pointer;
      transition: filter 0.2s, box-shadow 0.2s;

      &:hover { filter: brightness(1.15); }

      &.search-match {
        background: rgba(59, 130, 246, 0.45);
      }

      &.query-hit {
        background: rgba(34, 197, 94, 0.55);
        box-shadow: inset 0 0 0 1px rgba(34, 197, 94, 0.8);
      }

      &.best-match {
        background: linear-gradient(180deg, rgba(34, 197, 94, 0.95), rgba(22, 163, 74, 0.85));
        box-shadow: inset 0 -2px 0 rgba(255, 255, 255, 0.35);
      }

      .seg-pin {
        position: absolute;
        top: 2px;
        left: 50%;
        transform: translateX(-50%);
        font-size: 0.85rem;
        width: 0.85rem;
        height: 0.85rem;
        color: #052e16;
      }
    }

    .timeline-legend {
      display: flex;
      gap: 0.75rem;
      margin-top: 0.35rem;
      font-size: 0.68rem;
      color: var(--text-muted);
    }

    .legend-item {
      display: inline-flex;
      align-items: center;
      gap: 0.3rem;
    }

    .dot {
      width: 8px;
      height: 8px;
      border-radius: 2px;
      display: inline-block;

      &.best { background: #22c55e; }
      &.hit { background: rgba(34, 197, 94, 0.55); }
    }

    .reasoning-content {
      display: flex;
      gap: 0.6rem;
      background: rgba(6, 255, 165, 0.05);
      border: 1px solid rgba(6, 255, 165, 0.18);
      border-radius: 10px;
      padding: 0.65rem;
      margin-bottom: 0.65rem;

      .reasoning-icon {
        color: rgba(6, 255, 165, 0.85);
        flex-shrink: 0;
      }

      p {
        margin: 0;
        font-size: 0.85rem;
        line-height: 1.45;
        color: var(--text-secondary);
        display: -webkit-box;
        -webkit-line-clamp: 3;
        -webkit-box-orient: vertical;
        overflow: hidden;

        ::ng-deep .query-term-text {
          color: #22c55e;
          font-weight: 600;
        }
      }
    }

    .object-tags {
      display: flex;
      flex-wrap: wrap;
      gap: 0.35rem;
      margin-bottom: 0.65rem;
      min-height: 1.25rem;
    }

    .object-chip {
      font-size: 0.7rem;
      padding: 0.15rem 0.45rem;
      border-radius: 999px;
      background: var(--bg-secondary);
      border: 1px solid var(--border-color);
      color: var(--text-secondary);

      &.highlight {
        color: #22c55e;
        font-weight: 600;
      }
    }

    .video-metadata {
      display: flex;
      flex-wrap: wrap;
      gap: 0.4rem;
      margin-bottom: 0.75rem;

      .metadata-item {
        display: inline-flex;
        align-items: center;
        gap: 0.25rem;
        font-size: 0.75rem;
        color: var(--text-secondary);
        background: var(--bg-secondary);
        padding: 0.2rem 0.5rem;
        border-radius: 999px;

        mat-icon {
          font-size: 0.9rem;
          width: 0.9rem;
          height: 0.9rem;
        }
      }
    }

    .open-btn {
      width: 100%;
      border-color: rgba(34, 197, 94, 0.45) !important;
      color: #22c55e !important;
    }
  `],
})
export class ChunkCardComponent implements OnChanges {
  private videoService = inject(VideoService);
  private sanitizer = inject(DomSanitizer);

  @Input({ required: true }) chunk!: ChunkSearchResult;
  @Output() open = new EventEmitter<ChunkSearchResult>();
  @Output() jumpTo = new EventEmitter<{ chunk: ChunkSearchResult; seekSec: number }>();

  @ViewChild('videoElement') videoElement?: ElementRef<HTMLVideoElement>;

  previewUrl = '';
  isPlaying = false;
  private queryTerms: string[] = [];

  ngOnChanges(changes: SimpleChanges) {
    if (changes['chunk']) {
      this.syncFromChunk();
    }
  }

  private syncFromChunk() {
    const token = localStorage.getItem('video_lab_token');
    if (token) {
      this.previewUrl = this.videoService.getStreamUrl(this.chunk.preview_source, token);
    }
    this.queryTerms = extractHighlightTerms(this.chunk.query);
  }

  cardCaption(): string {
    return previewCaption(this.chunk);
  }

  onOpen(event?: Event) {
    event?.stopPropagation();
    this.open.emit(this.chunk);
  }

  onSegmentClick(event: Event, seekSec: number) {
    event.stopPropagation();
    this.jumpTo.emit({ chunk: this.chunk, seekSec });
  }

  segmentFlex(seg: ChunkSearchResult['timeline'][0]): string {
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

  segmentTooltip(seg: ChunkSearchResult['timeline'][0]): string {
    const parts = [
      `#${seg.segment_number} ${this.formatTime(seg.segment_start_sec)}–${this.formatTime(seg.segment_end_sec)}`,
    ];
    if (seg.object_classes?.trim()) parts.push(seg.object_classes);
    return parts.join(' · ');
  }

  highlightHtml(text: string): SafeHtml {
    if (!text) return '';
    const html = highlightQueryTerms(text, this.queryTerms);
    return this.sanitizer.bypassSecurityTrustHtml(html);
  }

  objectTags(): string[] {
    const tags = new Set<string>();
    for (const seg of this.chunk.timeline) {
      for (const obj of parseStructuredObjects(seg)) {
        tags.add(obj);
      }
    }
    return Array.from(tags).slice(0, 8);
  }

  isQueryTerm(label: string): boolean {
    return objectMatchesQuery(label, this.queryTerms);
  }

  onVideoLoaded() {
    // preview ready
  }

  async onHoverStart() {
    const video = this.videoElement?.nativeElement;
    if (!video) return;
    try {
      await video.play();
      this.isPlaying = true;
    } catch {
      // autoplay blocked
    }
  }

  onHoverEnd() {
    const video = this.videoElement?.nativeElement;
    if (!video) return;
    video.pause();
    video.currentTime = 0;
    this.isPlaying = false;
  }
}
