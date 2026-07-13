import { Component, OnDestroy, OnInit, computed, inject, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { MatButtonModule } from '@angular/material/button';
import { MatCardModule } from '@angular/material/card';
import { MatIconModule } from '@angular/material/icon';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { MatSlideToggleModule } from '@angular/material/slide-toggle';
import { MatTooltipModule } from '@angular/material/tooltip';
import { Subscription, interval } from 'rxjs';
import { DashboardService } from '../../shared/services/dashboard.service';
import { PageRefreshService } from '../../shared/services/page-refresh.service';
import { SuggestionsService } from '../../shared/services/suggestions.service';
import {
  DashboardScope,
  DashboardStatsResponse,
  UploadDayItem,
} from '../../shared/models/dashboard.model';
import { KeyEventSuggestion } from '../../shared/models/suggestions.model';
import { KeyEventSearchFloatComponent } from './components/key-event-search-float.component';
import { ScopePillsComponent } from '../../shared/components/scope-pills.component';
import { formatAbsoluteTime, formatRelativeTime } from '../../shared/utils/time.util';
import {
  friendlyVastDbAccessMessage,
  resolveApiAccessWarning,
} from '../../shared/utils/api-access.util';
import { IngestMetadataService } from '../../shared/services/ingest-metadata.service';
import { relativeBarWidth } from '../../shared/utils/chunk-display.util';

interface DashboardKpiCard {
  label: string;
  value: number | string;
  hint: string;
  warn?: boolean;
}

@Component({
  selector: 'app-dashboard-page',
  standalone: true,
  imports: [
    CommonModule,
    MatButtonModule,
    MatCardModule,
    MatIconModule,
    MatProgressSpinnerModule,
    MatSlideToggleModule,
    MatTooltipModule,
    KeyEventSearchFloatComponent,
    ScopePillsComponent,
  ],
  template: `
    <div class="dashboard-page">
      <header class="page-header">
        <div class="title-block">
          <h1>
            <mat-icon>dashboard</mat-icon>
            Data Dashboard
          </h1>
          <p>Live view of what is stored in VastDB — segments, objects, metadata, and ingest health.</p>
        </div>
      </header>

      <div class="toolbar-card">
        <app-scope-pills
          label="Show data:"
          [scope]="scope()"
          (scopeChange)="setScope($event)">
        </app-scope-pills>
        <div class="toolbar-actions">
          <mat-slide-toggle class="dash-toggle" [checked]="autoRefresh()" (change)="toggleAutoRefresh($event.checked)">
            Auto-refresh (30s)
          </mat-slide-toggle>
          <button mat-stroked-button class="dash-btn" (click)="loadStats()" [disabled]="loading()">
            <mat-icon>refresh</mat-icon>
            Refresh
          </button>
        </div>
      </div>

      @if (accessWarning() && !stats()) {
        <div class="access-warn-panel">
          <mat-icon>warning_amber</mat-icon>
          <div>
            <p>{{ accessWarning() }}</p>
            <span class="access-hint">Upload a video or confirm <code>vss-collection</code> exists in VastDB.</span>
          </div>
        </div>
      }

      @if (stats()?.table_message) {
        <div class="info-banner" [class.warn]="!stats()?.table_available">
          <mat-icon>{{ stats()?.table_available ? 'info' : 'warning_amber' }}</mat-icon>
          <span>{{ stats()!.table_message }}</span>
        </div>
      }

      @if (loading() && !stats()) {
        <div class="loading-state">
          <mat-spinner diameter="48"></mat-spinner>
          <p>Loading VastDB statistics…</p>
        </div>
      }

      @if (stats(); as data) {
        @if (loading()) {
          <div class="refresh-indicator">
            <mat-spinner diameter="20"></mat-spinner>
            <span>Refreshing…</span>
          </div>
        }

        <div class="meta-chips">
          <span class="meta-chip"><mat-icon>table_chart</mat-icon>{{ data.table }}</span>
          <span class="meta-chip"><mat-icon>filter_list</mat-icon>Scope: {{ data.scope }}</span>
          <span class="meta-chip"><mat-icon>schedule</mat-icon>{{ formatTimestamp(data.generated_at) }}</span>
          <span class="meta-chip"><mat-icon>speed</mat-icon>{{ data.query_time_ms.toFixed(0) }} ms</span>
        </div>

        @if (data.table_available) {
        <section class="kpi-grid">
          @for (card of kpiCards(data); track card.label) {
            <mat-card class="kpi-card" [class.warn]="card.warn">
              <div class="kpi-value">{{ card.value }}</div>
              <div class="kpi-label">{{ card.label }}</div>
              @if (card.hint) {
                <div class="kpi-hint">{{ card.hint }}</div>
              }
            </mat-card>
          }
        </section>
        }

        @if (data.s3_inventory?.errors && data.table_available) {
          <div class="info-banner warn">
            <mat-icon>warning_amber</mat-icon>
            <span>Could not read some S3 buckets: {{ formatS3Errors(data.s3_inventory!.errors!) }}</span>
          </div>
        }

        @if (data.table_available) {
        <section class="panel-grid">
          <mat-card class="panel">
            <mat-card-header>
              <mat-card-title>Ingest quality</mat-card-title>
            </mat-card-header>
            <mat-card-content>
              <div class="quality-row">
                <span>Structured JSON parsed</span>
                <strong>{{ data.quality.structured_parse_ok_pct }}%</strong>
                <span class="muted">({{ data.quality.structured_parse_ok }}/{{ data.overview.segment_rows }})</span>
              </div>
              <div class="quality-bar"><div class="fill" [style.width.%]="data.quality.structured_parse_ok_pct"></div></div>
              <div class="quality-row">
                <span>Detector coverage</span>
                <strong>{{ data.quality.perception_ok_pct }}%</strong>
                <span class="muted">({{ data.quality.perception_ok }}/{{ data.overview.segment_rows }})</span>
              </div>
              <div class="quality-bar"><div class="fill perception" [style.width.%]="data.quality.perception_ok_pct"></div></div>
              <div class="quality-row">
                <span>Rows with object classes</span>
                <strong>{{ data.quality.with_object_classes_pct }}%</strong>
                <span class="muted">({{ data.quality.with_object_classes }}/{{ data.overview.segment_rows }})</span>
              </div>
              <div class="quality-bar"><div class="fill objects" [style.width.%]="data.quality.with_object_classes_pct"></div></div>
            </mat-card-content>
          </mat-card>

          <mat-card class="panel">
            <mat-card-header>
              <mat-card-title>Uploads over time</mat-card-title>
              <mat-card-subtitle>Segment rows by upload day</mat-card-subtitle>
            </mat-card-header>
            <mat-card-content>
              @if (data.uploads_by_day.length) {
                <div class="timeline-chart">
                  @for (day of data.uploads_by_day; track day.date) {
                    <div class="timeline-bar-row" [matTooltip]="day.date + ': ' + day.segment_rows + ' rows'">
                      <span class="day-label">{{ shortDate(day.date) }}</span>
                      <div class="bar-track">
                        <div class="bar-fill" [style.width.%]="barWidth(day, data.uploads_by_day)"></div>
                      </div>
                      <span class="day-count">{{ day.segment_rows }}</span>
                    </div>
                  }
                </div>
              } @else {
                <p class="empty-panel">No upload timestamps found.</p>
              }
            </mat-card-content>
          </mat-card>
        </section>

        <section class="panel-grid">
          <mat-card class="panel">
            <mat-card-header>
              <mat-card-title>Object detection heatmap</mat-card-title>
              <mat-card-subtitle>How many segments contain each class (YOLO)</mat-card-subtitle>
            </mat-card-header>
            <mat-card-content>
              @if (data.objects.length) {
                <div class="object-heatmap-scroll">
                  <div class="object-heatmap">
                    @for (obj of data.objects; track obj.label) {
                      <div class="heatmap-row" [matTooltip]="obj.segment_count + ' segments with ' + obj.label">
                        <span class="heatmap-label">{{ obj.label }}</span>
                        <div class="heatmap-track">
                          <div
                            class="heatmap-fill"
                            [style.width.%]="objectBarWidth(obj, data.objects)">
                          </div>
                        </div>
                        <span class="heatmap-count">{{ obj.segment_count }}</span>
                        <span class="heatmap-gutter" aria-hidden="true"></span>
                      </div>
                    }
                  </div>
                </div>
              } @else {
                <p class="empty-panel">No object_classes populated yet.</p>
              }
            </mat-card-content>
          </mat-card>

          <mat-card class="panel">
            <mat-card-header>
              <mat-card-title>Upload metadata</mat-card-title>
              <mat-card-subtitle>camera_id · capture_type · location</mat-card-subtitle>
            </mat-card-header>
            <mat-card-content class="metadata-columns">
              @for (field of metadataFields(); track field.key) {
                <div class="metadata-block">
                  <h3>{{ field.label }}</h3>
                  @if (data.metadata[field.key]?.length) {
                    @for (item of data.metadata[field.key]; track item.label) {
                      <div class="metadata-row">
                        <span class="metadata-label" [matTooltip]="item.label">{{ formatMetadataLabel(item.label) }}</span>
                        <strong>{{ item.count }}</strong>
                      </div>
                    }
                  } @else {
                    <p class="empty-panel">No values</p>
                  }
                </div>
              }
            </mat-card-content>
          </mat-card>
        </section>
        }

        <mat-card class="panel key-events-panel">
          <mat-card-header>
            <mat-card-title>Key events</mat-card-title>
            <mat-card-subtitle>
              {{ keyEvents().length }} events — search icon opens the event clip
              @if (suggestionsGeneratedAt()) {
                · updated {{ formatRelativeTime(suggestionsGeneratedAt()) }}
              }
            </mat-card-subtitle>
          </mat-card-header>
          <mat-card-content class="table-wrap table-scroll-viewport table-scroll-viewport-events">
            @if (keyEvents().length) {
              <table class="data-table key-events-table">
                <thead>
                  <tr>
                    <th class="col-action"></th>
                    <th>Event</th>
                    <th>Uploaded</th>
                    <th>Video</th>
                  </tr>
                </thead>
                <tbody>
                  @for (ev of keyEvents(); track eventTrackKey(ev)) {
                    <tr class="key-event-row">
                      <td class="col-action">
                        <button
                          type="button"
                          class="event-search-btn"
                          (click)="searchKeyEvent(ev)"
                          [matTooltip]="'Search & preview: ' + ev.query_text"
                          aria-label="Search this event">
                          <mat-icon>search</mat-icon>
                        </button>
                      </td>
                      <td class="col-event">
                        <mat-icon class="row-icon">bolt</mat-icon>
                        <div class="event-text">
                          <strong>{{ eventHeadline(ev) }}</strong>
                          @if (eventSubline(ev)) {
                            <span class="event-query">{{ eventSubline(ev) }}</span>
                          }
                        </div>
                      </td>
                      <td class="col-time" [matTooltip]="formatTimestamp(ev.upload_timestamp)">
                        {{ formatKeyEventUploaded(ev) }}
                      </td>
                      <td class="col-muted" [matTooltip]="ev.filename || ev.original_video">
                        {{ truncate(ev.filename || ev.original_video, 32) }}
                      </td>
                    </tr>
                  }
                </tbody>
              </table>
            } @else if (keyEventsAccessWarning()) {
              <p class="empty-panel access-hint-warn">
                <mat-icon>warning_amber</mat-icon>
                {{ keyEventsAccessWarning() }}
              </p>
            } @else if (promptsTableAvailable() === false) {
              <p class="empty-panel access-hint-warn">
                <mat-icon>warning_amber</mat-icon>
                {{ promptsTableMessage() || 'Could not read prompts table. Check backend logs and VastDB access.' }}
              </p>
            } @else {
              <p class="empty-panel">
                No key events yet. Run the prompt-suggester scheduled function after segments are indexed.
              </p>
            }
          </mat-card-content>
        </mat-card>

        @if (data.table_available) {
        <mat-card class="panel recent-panel">
          <mat-card-header>
            <mat-card-title>Recent videos in index</mat-card-title>
            <mat-card-subtitle>
              Indexed groups · {{ data.recent_videos.length }}
              @if (data.overview.stream_sessions) {
                · {{ data.overview.stream_sessions }} stream sessions
              }
            </mat-card-subtitle>
          </mat-card-header>
          <mat-card-content class="table-wrap table-scroll-viewport">
            @if (data.recent_videos.length) {
              <table class="data-table">
                <thead>
                  <tr>
                    <th>Video / stream</th>
                    <th>Indexed clips</th>
                    <th>Location</th>
                    <th>Camera</th>
                    <th>Capture</th>
                    <th>Access</th>
                    <th>Uploaded</th>
                  </tr>
                </thead>
                <tbody>
                  @for (row of data.recent_videos; track row.stream_id || row.original_video) {
                    <tr>
                      <td class="col-video">
                        <mat-icon class="row-icon">{{ row.stream_id ? 'live_tv' : 'movie' }}</mat-icon>
                        <span [matTooltip]="row.original_video">{{ truncate(row.filename, 36) }}</span>
                      </td>
                      <td>
                        <span class="seg-count">{{ row.indexed_clips ?? row.unique_segments }}</span>
                        <span class="muted"> clips</span>
                        @if (row.chunk_count) {
                          <span class="muted"> · {{ row.chunk_count }} chunks</span>
                        }
                        @if (row.stream_span_sec) {
                          <span class="muted"> · {{ formatEventTime(row.stream_span_sec) }} span</span>
                        }
                        @if ((row.re_ingest_rows ?? row.duplicate_rows) > 0) {
                          <span class="dup-badge" matTooltip="Same segment file indexed more than once">{{ row.re_ingest_rows ?? row.duplicate_rows }} re-ingest</span>
                        }
                      </td>
                      <td class="col-muted" [matTooltip]="row.location">{{ formatMetadataLabel(row.location) }}</td>
                      <td class="col-muted">{{ formatMetadataLabel(row.camera_id) }}</td>
                      <td class="col-muted">{{ formatMetadataLabel(row.capture_type) }}</td>
                      <td>
                        <span class="access-pill" [class.public]="row.is_public">
                          <mat-icon>{{ row.is_public ? 'public' : 'lock' }}</mat-icon>
                          {{ row.is_public ? 'Public' : 'Private' }}
                        </span>
                      </td>
                      <td class="col-muted">{{ formatTimestamp(row.upload_timestamp) }}</td>
                    </tr>
                  }
                </tbody>
              </table>
            } @else {
              <p class="empty-panel">No indexed videos for this scope.</p>
            }
          </mat-card-content>
        </mat-card>
        }
      }
    </div>

    <app-key-event-search-float
      [event]="activeKeyEvent()"
      (closed)="onKeyEventFloatClosed()">
    </app-key-event-search-float>
  `,
  styles: [`
    .dashboard-page {
      max-width: 1280px;
      margin: 0 auto;
      padding: 0 1.5rem 2.5rem;
    }

    .page-header {
      margin-bottom: 1rem;
    }

    .title-block h1 {
      display: flex;
      align-items: center;
      gap: 0.5rem;
      margin: 0 0 0.35rem;
      font-size: 1.5rem;
      color: var(--text-primary);

      mat-icon {
        color: var(--accent-primary);
      }
    }

    .title-block p {
      margin: 0;
      color: var(--text-secondary);
      max-width: 42rem;
      line-height: 1.5;
    }

    .toolbar-card {
      display: flex;
      flex-wrap: wrap;
      gap: 1rem;
      justify-content: space-between;
      align-items: center;
      padding: 1rem 1.25rem;
      margin-bottom: 1rem;
      background: var(--bg-card);
      border: 1px solid var(--border-color);
      border-radius: 12px;
    }

    .toolbar-actions {
      display: flex;
      flex-wrap: wrap;
      gap: 0.75rem;
      align-items: center;
    }

    .dash-btn {
      color: var(--text-primary) !important;
      border-color: var(--border-color) !important;
      background: var(--bg-secondary) !important;
      height: 38px;

      mat-icon {
        margin-right: 0.25rem;
        font-size: 18px;
        width: 18px;
        height: 18px;
        color: var(--accent-primary);
      }

      &:hover:not([disabled]) {
        border-color: var(--border-hover) !important;
        background: var(--bg-card-hover) !important;
      }
    }

    .dash-toggle {
      ::ng-deep .mdc-label {
        color: var(--text-secondary) !important;
        font-size: 0.875rem;
      }

      ::ng-deep .mdc-switch__track::after {
        background: var(--accent-primary) !important;
      }
    }

    .meta-chips {
      display: flex;
      flex-wrap: wrap;
      gap: 0.5rem;
      margin-bottom: 1rem;
    }

    .meta-chip {
      display: inline-flex;
      align-items: center;
      gap: 0.35rem;
      padding: 0.35rem 0.75rem;
      border-radius: 999px;
      background: var(--bg-secondary);
      border: 1px solid var(--border-color);
      color: var(--text-secondary);
      font-size: 0.78rem;

      mat-icon {
        font-size: 14px;
        width: 14px;
        height: 14px;
        color: var(--accent-primary);
      }
    }

    .refresh-indicator {
      display: flex;
      align-items: center;
      gap: 0.5rem;
      margin-bottom: 0.75rem;
      color: var(--text-secondary);
      font-size: 0.85rem;
    }

    .kpi-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(148px, 1fr));
      gap: 0.75rem;
      margin-bottom: 1rem;
    }

    .kpi-card {
      padding: 1rem 1.1rem;
      background: var(--bg-card) !important;
      border: 1px solid var(--border-color);
      border-radius: 10px;
      box-shadow: none !important;
    }

    .kpi-card.warn {
      border-color: rgba(232, 175, 111, 0.45);
      background: linear-gradient(135deg, var(--bg-card) 0%, rgba(232, 175, 111, 0.06) 100%) !important;
    }

    .kpi-value {
      font-size: 1.65rem;
      font-weight: 700;
      color: var(--accent-primary);
      line-height: 1.1;
    }

    .kpi-card.warn .kpi-value { color: var(--accent-warning); }

    .kpi-label {
      margin-top: 0.35rem;
      font-size: 0.85rem;
      color: var(--text-primary);
      font-weight: 500;
    }

    .kpi-hint {
      margin-top: 0.25rem;
      font-size: 0.72rem;
      color: var(--text-muted);
      line-height: 1.3;
    }

    .panel-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
      gap: 1rem;
      margin-bottom: 1rem;
    }

    .panel, .recent-panel {
      background: var(--bg-card) !important;
      border: 1px solid var(--border-color);
      border-radius: 12px;
      box-shadow: none !important;
    }

    .panel ::ng-deep .mat-mdc-card-header,
    .recent-panel ::ng-deep .mat-mdc-card-header {
      padding: 1rem 1.25rem 0;
    }

    .panel ::ng-deep .mat-mdc-card-title,
    .recent-panel ::ng-deep .mat-mdc-card-title {
      color: var(--text-primary) !important;
      font-size: 1rem !important;
      font-weight: 600 !important;
    }

    .panel ::ng-deep .mat-mdc-card-subtitle,
    .recent-panel ::ng-deep .mat-mdc-card-subtitle {
      color: var(--text-muted) !important;
      font-size: 0.8rem !important;
    }

    .panel ::ng-deep .mat-mdc-card-content,
    .recent-panel ::ng-deep .mat-mdc-card-content {
      padding: 0.75rem 1.25rem 1.25rem;
    }

    .quality-row {
      display: flex;
      align-items: baseline;
      gap: 0.5rem;
      margin-top: 0.75rem;
      font-size: 0.88rem;
      color: var(--text-primary);
    }

    .quality-bar {
      height: 6px;
      background: rgba(255, 255, 255, 0.06);
      border-radius: 999px;
      margin-top: 0.35rem;
      overflow: hidden;
    }

    .quality-bar .fill {
      height: 100%;
      background: var(--accent-primary);
      border-radius: 999px;
      transition: width 0.4s ease;
    }

    .quality-bar .fill.perception { background: #7c4dff; }
    .quality-bar .fill.objects { background: var(--accent-success); }

    .timeline-chart { display: flex; flex-direction: column; gap: 0.5rem; }

    .timeline-bar-row {
      display: grid;
      grid-template-columns: 4.5rem 1fr 2rem;
      gap: 0.5rem;
      align-items: center;
      font-size: 0.8rem;
    }

    .bar-track {
      height: 10px;
      background: rgba(255, 255, 255, 0.06);
      border-radius: 999px;
      overflow: hidden;
    }

    .bar-fill {
      height: 100%;
      background: linear-gradient(90deg, var(--accent-primary), var(--accent-success));
      border-radius: 999px;
      min-width: 2px;
      transition: width 0.4s ease;
    }

    .day-label, .day-count { color: var(--text-secondary); }

    .tag-grid {
      display: flex;
      flex-wrap: wrap;
      gap: 0.45rem;
    }

    .tag-stat {
      display: inline-flex;
      align-items: center;
      gap: 0.45rem;
      padding: 0.35rem 0.7rem;
      border-radius: 999px;
      border: 1px solid var(--border-color);
      background: rgba(115, 200, 253, 0.08);
      font-size: 0.82rem;
      color: var(--text-primary);
    }

    .tag-count {
      font-weight: 700;
      color: var(--accent-primary);
    }

    .object-heatmap-scroll {
      max-height: calc(1.75rem * 8 + 0.45rem * 7);
      overflow-y: auto;
      overflow-x: hidden;
      scrollbar-gutter: stable;
      box-sizing: border-box;
      scrollbar-width: thin;
      scrollbar-color: rgba(115, 200, 253, 0.45) transparent;

      &::-webkit-scrollbar {
        width: 6px;
      }

      &::-webkit-scrollbar-track {
        margin-top: 2px;
        margin-bottom: 2px;
      }

      &::-webkit-scrollbar-thumb {
        background: rgba(115, 200, 253, 0.35);
        border-radius: 999px;
      }
    }

    .object-heatmap {
      display: flex;
      flex-direction: column;
      gap: 0.45rem;
    }

    .heatmap-row {
      display: grid;
      grid-template-columns: 6.5rem minmax(0, 1fr) 2.5rem 0.75rem;
      gap: 0.5rem;
      align-items: center;
      min-height: 1.75rem;
      font-size: 0.82rem;
    }

    .heatmap-label {
      color: var(--text-primary);
      text-transform: capitalize;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }

    .heatmap-track {
      height: 12px;
      background: rgba(255, 255, 255, 0.06);
      border-radius: 999px;
      overflow: hidden;
    }

    .heatmap-fill {
      height: 100%;
      border-radius: 999px;
      background: linear-gradient(90deg, rgba(34, 197, 94, 0.55), rgba(34, 197, 94, 0.95));
      min-width: 2px;
      transition: width 0.35s ease;
    }

    .heatmap-count {
      text-align: right;
      font-weight: 600;
      color: var(--accent-success);
      font-variant-numeric: tabular-nums;
    }

    .heatmap-gutter {
      width: 100%;
      min-height: 1px;
    }

    .metadata-columns {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
      gap: 1rem;
    }

    .metadata-block h3 {
      margin: 0 0 0.5rem;
      font-size: 0.72rem;
      color: var(--text-muted);
      text-transform: uppercase;
      letter-spacing: 0.06em;
      font-weight: 600;
    }

    .metadata-row {
      display: grid;
      grid-template-columns: 1fr auto;
      gap: 0.75rem;
      align-items: start;
      font-size: 0.82rem;
      padding: 0.35rem 0;
      border-bottom: 1px solid rgba(255, 255, 255, 0.04);
      color: var(--text-primary);

      strong {
        color: var(--accent-primary);
        font-weight: 600;
      }
    }

    .metadata-label {
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
      min-width: 0;
    }

    .table-wrap {
      border: 1px solid var(--border-color);
      border-radius: 10px;
      background: var(--bg-secondary);
    }

    .table-scroll-viewport {
      max-height: calc(2.85rem * 11);
      overflow: auto;
    }

    .table-scroll-viewport-events {
      max-height: calc(4.25rem * 10);
    }

    .table-scroll-viewport thead th {
      position: sticky;
      top: 0;
      z-index: 2;
      background: var(--bg-header);
    }

    .data-table {
      width: 100%;
      border-collapse: collapse;
      font-size: 0.84rem;
    }

    .data-table thead {
      background: var(--bg-header);
    }

    .data-table th {
      padding: 0.75rem 1rem;
      text-align: left;
      font-size: 0.7rem;
      font-weight: 600;
      text-transform: uppercase;
      letter-spacing: 0.05em;
      color: var(--text-muted);
      border-bottom: 1px solid var(--border-color);
      white-space: nowrap;
    }

    .data-table td {
      padding: 0.7rem 1rem;
      color: var(--text-primary);
      border-bottom: 1px solid rgba(255, 255, 255, 0.04);
      vertical-align: middle;
    }

    .data-table tbody tr {
      transition: background 0.15s ease;

      &:hover {
        background: var(--bg-card-hover);
      }

      &:last-child td {
        border-bottom: none;
      }
    }

    .col-video {
      display: flex;
      align-items: center;
      gap: 0.5rem;
      font-weight: 500;
      min-width: 10rem;
    }

    .row-icon {
      font-size: 18px;
      width: 18px;
      height: 18px;
      color: var(--accent-primary);
      flex-shrink: 0;
    }

    .col-muted {
      color: var(--text-secondary);
      max-width: 14rem;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }

    .seg-count {
      font-weight: 600;
      color: var(--accent-primary);
    }

    .access-pill {
      display: inline-flex;
      align-items: center;
      gap: 0.25rem;
      padding: 0.2rem 0.55rem;
      border-radius: 999px;
      font-size: 0.75rem;
      background: rgba(255, 255, 255, 0.06);
      color: var(--text-secondary);
      border: 1px solid var(--border-color);

      mat-icon {
        font-size: 14px;
        width: 14px;
        height: 14px;
      }

      &.public {
        background: rgba(115, 200, 253, 0.12);
        color: var(--accent-primary);
        border-color: rgba(115, 200, 253, 0.25);
      }
    }

    .dup-badge {
      margin-left: 0.35rem;
      padding: 0.12rem 0.4rem;
      border-radius: 4px;
      background: rgba(232, 175, 111, 0.15);
      color: var(--accent-warning);
      font-size: 0.68rem;
      font-weight: 600;
    }

    .muted { color: var(--text-muted); }

    .empty-panel {
      color: var(--text-muted);
      font-size: 0.88rem;
      font-style: italic;
      padding: 0.5rem 0;
    }

    .key-events-panel {
      margin-bottom: 1rem;
    }

    .key-events-table .key-event-row {
      transition: background 0.15s ease;
    }

    .col-action {
      width: 3rem;
      padding-right: 0.25rem !important;
    }

    .event-search-btn {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      width: 2rem;
      height: 2rem;
      padding: 0;
      border: 1px solid var(--border-color);
      border-radius: 10px;
      background: var(--bg-secondary);
      color: var(--accent-primary);
      cursor: pointer;
      transition: background 0.2s ease, border-color 0.2s ease, transform 0.15s ease;

      mat-icon {
        font-size: 1.1rem;
        width: 1.1rem;
        height: 1.1rem;
        pointer-events: none;
      }

      &:hover {
        background: rgba(115, 200, 253, 0.15);
        border-color: var(--accent-primary);
        transform: translateY(-1px);
      }

      &:active {
        transform: translateY(0);
      }
    }

    .col-event {
      display: flex;
      align-items: flex-start;
      gap: 0.5rem;
      min-width: 14rem;
    }

    .event-text {
      display: flex;
      flex-direction: column;
      gap: 0.2rem;

      strong {
        color: var(--text-primary);
        font-size: 0.88rem;
      }
    }

    .event-query {
      color: var(--text-muted);
      font-size: 0.78rem;
      line-height: 1.35;
    }

    .col-time {
      white-space: nowrap;
      color: var(--accent-primary);
      font-variant-numeric: tabular-nums;
      font-size: 0.85rem;
    }

    .loading-state {
      display: flex;
      align-items: center;
      justify-content: center;
      gap: 0.75rem;
      padding: 2rem;
      color: var(--text-secondary);
    }

    .access-warn-panel {
      display: flex;
      align-items: flex-start;
      gap: 0.75rem;
      margin-bottom: 1rem;
      padding: 1rem 1.15rem;
      border: 1px solid rgba(232, 175, 111, 0.45);
      border-radius: 12px;
      background: rgba(232, 175, 111, 0.1);
      color: var(--text-secondary);

      mat-icon {
        color: var(--accent-warning, #e8af6f);
        flex-shrink: 0;
      }

      p {
        margin: 0 0 0.35rem;
        color: var(--text-primary);
        font-weight: 500;
      }

      .access-hint {
        font-size: 0.88rem;
        color: var(--text-muted);

        code {
          color: var(--accent-primary);
          font-size: 0.82rem;
        }
      }
    }

    .access-hint-warn {
      display: flex;
      align-items: flex-start;
      gap: 0.5rem;
      color: var(--accent-warning, #e8af6f);

      mat-icon {
        font-size: 1.1rem;
        width: 1.1rem;
        height: 1.1rem;
        flex-shrink: 0;
      }
    }

    .info-banner {
      display: flex;
      align-items: flex-start;
      gap: 0.6rem;
      margin-bottom: 1rem;
      padding: 0.75rem 1rem;
      border: 1px solid rgba(115, 200, 253, 0.35);
      border-radius: 8px;
      background: rgba(115, 200, 253, 0.08);
      color: var(--text-secondary);
      font-size: 0.9rem;
      line-height: 1.45;

      mat-icon {
        color: var(--accent-primary);
        flex-shrink: 0;
        margin-top: 1px;
      }

      &.warn {
        border-color: rgba(232, 175, 111, 0.4);
        background: rgba(232, 175, 111, 0.08);

        mat-icon { color: var(--accent-warning); }
      }
    }
  `],
})
export class DashboardPageComponent implements OnInit, OnDestroy {
  private dashboardService = inject(DashboardService);
  private metadataService = inject(IngestMetadataService);
  private suggestionsService = inject(SuggestionsService);
  private pageRefresh = inject(PageRefreshService);

  stats = signal<DashboardStatsResponse | null>(null);
  loading = signal(false);
  accessWarning = signal<string | null>(null);
  keyEventsAccessWarning = signal<string | null>(null);
  scope = signal<DashboardScope>('all');
  autoRefresh = signal(true);
  keyEvents = signal<KeyEventSuggestion[]>([]);
  activeKeyEvent = signal<KeyEventSuggestion | null>(null);
  suggestionsGeneratedAt = signal<string | null>(null);
  promptsTableAvailable = signal<boolean | null>(null);
  promptsTableMessage = signal<string | null>(null);

  metadataFields = computed(() =>
    (this.metadataService.config()?.filterable_fields ?? []).filter(f => f.key !== 'object_classes')
  );

  private refreshSub?: Subscription;
  private pageRefreshSub?: Subscription;
  private keyEventsSub?: Subscription;
  private static readonly KEY_EVENTS_POLL_MS = 300_000;

  ngOnInit() {
    void this.metadataService.ensureLoaded();
    this.loadStats();
    this.loadKeyEvents();
    this.refreshSub = interval(30_000).subscribe(() => {
      if (this.autoRefresh()) {
        this.loadStats(true);
      }
    });
    this.keyEventsSub = interval(DashboardPageComponent.KEY_EVENTS_POLL_MS).subscribe(() => {
      this.loadKeyEvents(true);
    });
    this.pageRefreshSub = this.pageRefresh.refresh$.subscribe(() => this.reloadView());
  }

  ngOnDestroy() {
    this.refreshSub?.unsubscribe();
    this.pageRefreshSub?.unsubscribe();
    this.keyEventsSub?.unsubscribe();
  }

  private reloadView() {
    this.loadStats();
    this.loadKeyEvents();
  }

  setScope(scope: DashboardScope) {
    this.scope.set(scope);
    this.loadStats();
  }

  toggleAutoRefresh(enabled: boolean) {
    this.autoRefresh.set(enabled);
  }

  loadStats(silent = false) {
    if (!silent) {
      this.loading.set(true);
      this.accessWarning.set(null);
    }
    this.dashboardService.getStats(this.scope()).subscribe({
      next: (data) => {
        this.stats.set(data);
        this.loading.set(false);
        if (data.table_available === false) {
          this.accessWarning.set(null);
        }
      },
      error: (err) => {
        this.accessWarning.set(resolveApiAccessWarning(err, 'dashboard'));
        this.stats.set(null);
        this.loading.set(false);
      },
    });
  }

  loadKeyEvents(silent = false) {
    if (!silent) {
      this.keyEventsAccessWarning.set(null);
    }
    this.suggestionsService.getSuggestions().subscribe({
      next: (data) => {
        const events = data.key_events ?? [];
        const genAt = data.generated_at ?? null;
        this.promptsTableAvailable.set(data.prompts_table_available ?? true);
        this.promptsTableMessage.set(data.table_message ?? null);
        if (data.prompts_table_available === false) {
          this.keyEvents.set([]);
          this.keyEventsAccessWarning.set(null);
          return;
        }
        if (silent && genAt === this.suggestionsGeneratedAt()) {
          return;
        }
        this.keyEvents.set(events);
        this.suggestionsGeneratedAt.set(genAt);
        this.keyEventsAccessWarning.set(null);
      },
      error: (err) => {
        this.keyEvents.set([]);
        this.keyEventsAccessWarning.set(resolveApiAccessWarning(err, 'suggestions'));
      },
    });
  }

  eventTrackKey(ev: KeyEventSuggestion): string {
    return `${ev.batch_id ?? ''}:${ev.query_text}:${ev.segment_start_sec}:${ev.original_video}`;
  }

  eventHeadline(ev: KeyEventSuggestion): string {
    const label = (ev.label || '').trim();
    const query = (ev.query_text || '').trim();
    if (label && label.toLowerCase() !== query.toLowerCase()) {
      return label;
    }
    return query;
  }

  eventSubline(ev: KeyEventSuggestion): string {
    const label = (ev.label || '').trim();
    const query = (ev.query_text || '').trim();
    if (label && label.toLowerCase() !== query.toLowerCase()) {
      return query;
    }
    return '';
  }

  searchKeyEvent(ev: KeyEventSuggestion) {
    this.activeKeyEvent.set(null);
    queueMicrotask(() => this.activeKeyEvent.set({ ...ev }));
  }

  onKeyEventFloatClosed() {
    this.activeKeyEvent.set(null);
  }

  formatEventTime(sec: number): string {
    if (!Number.isFinite(sec) || sec < 0) return '0:00';
    const m = Math.floor(sec / 60);
    const s = Math.floor(sec % 60);
    return `${m}:${s.toString().padStart(2, '0')}`;
  }

  formatKeyEventUploaded(ev: KeyEventSuggestion): string {
    if (ev.upload_timestamp) {
      return formatAbsoluteTime(ev.upload_timestamp);
    }
    return '—';
  }

  kpiCards(data: DashboardStatsResponse): DashboardKpiCard[] {
    const o = data.overview;
    const s3 = data.s3_inventory;
    const align = data.pipeline_alignment;
    const cards: DashboardKpiCard[] = [
      { label: 'Total rows', value: o.total_rows, hint: 'All accessible VastDB rows' },
      { label: 'Segment rows', value: o.segment_rows, hint: 'Searchable clip segments' },
      {
        label: 'Parent chunks',
        value: o.unique_videos,
        hint: 'Distinct original_video with ≥1 segment row (partial OK; each stream capture is its own parent)',
      },
      {
        label: 'Fully indexed parents',
        value: o.fully_indexed_videos ?? 0,
        hint: 'All segments 1..N in VastDB — Explore browse shows only these',
        warn: (o.fully_indexed_videos ?? 0) < o.unique_videos,
      },
      { label: 'Public segments', value: o.public_segment_rows, hint: 'is_public=true' },
      { label: 'Private segments', value: o.private_segment_rows, hint: 'Restricted access' },
      { label: 'Indexed clips', value: o.indexed_clips ?? o.segment_rows, hint: 'Unique segment files in VastDB' },
      { label: 'Stream sessions', value: o.stream_sessions ?? 0, hint: 'Distinct stream_id values' },
      {
        label: 'Re-ingest rows',
        value: o.re_ingest_rows ?? o.duplicate_segment_rows,
        hint: `${o.re_ingest_clips ?? o.duplicate_segment_slots} clips indexed more than once`,
        warn: (o.re_ingest_rows ?? o.duplicate_segment_rows) > 0,
      },
    ];
    if (s3 && data.table_available) {
      cards.splice(
        2,
        0,
        {
          label: 'S3 chunk MP4s',
          value: this.formatCount(s3.chunks_mp4),
          hint: s3.chunks_bucket,
        },
        {
          label: 'S3 segment MP4s',
          value: this.formatCount(align?.segments_s3_mp4 ?? s3.segments_mp4),
          hint: s3.segments_bucket,
        },
      );
    }
    return cards;
  }

  formatCount(value?: number | null): string | number {
    return value == null ? '—' : value;
  }

  formatS3Errors(errors: Record<string, string>): string {
    return Object.entries(errors)
      .map(([bucket, msg]) => `${bucket}: ${msg}`)
      .join('; ');
  }

  barWidth(day: UploadDayItem, all: UploadDayItem[]): number {
    return relativeBarWidth(day.segment_rows, all.map(d => d.segment_rows));
  }

  objectBarWidth(obj: { segment_count: number }, all: { segment_count: number }[]): number {
    return relativeBarWidth(obj.segment_count, all.map(o => o.segment_count));
  }

  shortDate(isoDate: string): string {
    const parts = isoDate.split('-');
    return parts.length === 3 ? `${parts[1]}/${parts[2]}` : isoDate;
  }

  formatTimestamp(value?: string | null): string {
    return formatAbsoluteTime(value);
  }

  formatRelativeTime = formatRelativeTime;

  formatMetadataLabel(value?: string | null): string {
    const text = (value || '').trim();
    if (!text || text === '(empty)') return 'Not set';
    if (text.startsWith('http://') || text.startsWith('https://')) {
      try {
        const url = new URL(text);
        return url.hostname + url.pathname.slice(0, 40) + (url.pathname.length > 40 ? '…' : '');
      } catch {
        return this.truncate(text, 48);
      }
    }
    return this.truncate(text, 48);
  }

  truncate(text: string, max: number): string {
    if (text.length <= max) return text;
    return text.slice(0, max - 1) + '…';
  }
}
