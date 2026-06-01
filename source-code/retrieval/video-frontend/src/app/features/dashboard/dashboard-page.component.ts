import { Component, OnDestroy, OnInit, inject, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterLink } from '@angular/router';
import { MatButtonModule } from '@angular/material/button';
import { MatCardModule } from '@angular/material/card';
import { MatIconModule } from '@angular/material/icon';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { MatSlideToggleModule } from '@angular/material/slide-toggle';
import { MatTooltipModule } from '@angular/material/tooltip';
import { MatSnackBar, MatSnackBarModule } from '@angular/material/snack-bar';
import { Subscription, interval } from 'rxjs';
import { DashboardService } from '../../shared/services/dashboard.service';
import { SuggestionsService } from '../../shared/services/suggestions.service';
import {
  DashboardScope,
  DashboardStatsResponse,
  UploadDayItem,
} from '../../shared/models/dashboard.model';
import { KeyEventSuggestion } from '../../shared/models/suggestions.model';

@Component({
  selector: 'app-dashboard-page',
  standalone: true,
  imports: [
    CommonModule,
    RouterLink,
    MatButtonModule,
    MatCardModule,
    MatIconModule,
    MatProgressSpinnerModule,
    MatSlideToggleModule,
    MatTooltipModule,
    MatSnackBarModule,
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
        <div class="scope-filter">
          <span class="scope-label">Show data:</span>
          <div class="scope-pills">
            <button type="button" class="scope-pill" [class.active]="scope() === 'all'" (click)="setScope('all')">
              <mat-icon>visibility</mat-icon>
              <span>All visible</span>
            </button>
            <button type="button" class="scope-pill" [class.active]="scope() === 'mine'" (click)="setScope('mine')">
              <mat-icon>person</mat-icon>
              <span>My uploads</span>
            </button>
            <button type="button" class="scope-pill" [class.active]="scope() === 'public'" (click)="setScope('public')">
              <mat-icon>public</mat-icon>
              <span>Public only</span>
            </button>
          </div>
        </div>
        <div class="toolbar-actions">
          <mat-slide-toggle class="dash-toggle" [checked]="autoRefresh()" (change)="toggleAutoRefresh($event.checked)">
            Auto-refresh (30s)
          </mat-slide-toggle>
          <button mat-stroked-button class="dash-btn" (click)="loadStats()" [disabled]="loading()">
            <mat-icon>refresh</mat-icon>
            Refresh
          </button>
          <a mat-stroked-button class="dash-btn" routerLink="/search">
            <mat-icon>search</mat-icon>
            Search
          </a>
        </div>
      </div>

      @if (error()) {
        <div class="error-banner">
          <mat-icon>error_outline</mat-icon>
          <span>{{ error() }}</span>
        </div>
      }

      @if (stats()?.table_message && !error()) {
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
                <span>Perception OK</span>
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
              <mat-card-title>Detected objects</mat-card-title>
              <mat-card-subtitle>Segments containing each object class</mat-card-subtitle>
            </mat-card-header>
            <mat-card-content>
              @if (data.objects.length) {
                <div class="tag-grid">
                  @for (obj of data.objects; track obj.label) {
                    <div class="tag-stat">
                      <span class="tag-label">{{ obj.label }}</span>
                      <span class="tag-count">{{ obj.segment_count }}</span>
                    </div>
                  }
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
              @for (field of metadataFields; track field.key) {
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

        <mat-card class="panel key-events-panel">
          <mat-card-header>
            <mat-card-title>Key events</mat-card-title>
            <mat-card-subtitle>
              LLM-suggested moments — click a row to copy the search query
              @if (suggestionsGeneratedAt()) {
                · updated {{ formatTimestamp(suggestionsGeneratedAt()) }}
              }
            </mat-card-subtitle>
          </mat-card-header>
          <mat-card-content class="key-events-scroll">
            @if (keyEvents().length) {
              <table class="data-table key-events-table">
                <thead>
                  <tr>
                    <th>Event</th>
                    <th>Time</th>
                    <th>Video</th>
                  </tr>
                </thead>
                <tbody>
                  @for (ev of keyEvents(); track ev.query_text + ev.segment_start_sec) {
                    <tr
                      class="key-event-row"
                      tabindex="0"
                      role="button"
                      (click)="copyKeyEvent(ev)"
                      (keydown.enter)="copyKeyEvent(ev)"
                      [matTooltip]="'Copy: ' + ev.query_text">
                      <td class="col-event">
                        <mat-icon class="row-icon">bolt</mat-icon>
                        <div class="event-text">
                          <strong>{{ ev.label || ev.query_text }}</strong>
                          <span class="event-query">{{ ev.query_text }}</span>
                        </div>
                      </td>
                      <td class="col-time">
                        {{ formatEventTime(ev.segment_start_sec) }} – {{ formatEventTime(ev.segment_end_sec) }}
                      </td>
                      <td class="col-muted" [matTooltip]="ev.filename || ev.original_video">
                        {{ truncate(ev.filename || ev.original_video, 32) }}
                      </td>
                    </tr>
                  }
                </tbody>
              </table>
            } @else {
              <p class="empty-panel">
                No key events yet. Run the prompt-suggester scheduled function after segments are indexed.
              </p>
            }
          </mat-card-content>
        </mat-card>

        <mat-card class="panel recent-panel">
          <mat-card-header>
            <mat-card-title>Recent videos in index</mat-card-title>
            <mat-card-subtitle>Grouped by original_video · {{ data.recent_videos.length }} videos</mat-card-subtitle>
          </mat-card-header>
          <mat-card-content class="table-wrap">
            @if (data.recent_videos.length) {
              <table class="data-table">
                <thead>
                  <tr>
                    <th>Video</th>
                    <th>Segments</th>
                    <th>Location</th>
                    <th>Camera</th>
                    <th>Capture</th>
                    <th>Access</th>
                    <th>Uploaded</th>
                  </tr>
                </thead>
                <tbody>
                  @for (row of data.recent_videos; track row.original_video) {
                    <tr>
                      <td class="col-video">
                        <mat-icon class="row-icon">movie</mat-icon>
                        <span [matTooltip]="row.filename">{{ truncate(row.filename, 36) }}</span>
                      </td>
                      <td>
                        <span class="seg-count">{{ row.unique_segments }}</span>
                        @if (row.expected_segments) {
                          <span class="muted">/ {{ row.expected_segments }}</span>
                        }
                        @if (row.duplicate_rows > 0) {
                          <span class="dup-badge" matTooltip="Extra rows from re-ingest">{{ row.duplicate_rows }} dup</span>
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
    </div>
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

    .scope-filter {
      display: flex;
      align-items: center;
      gap: 0.75rem;
      flex-wrap: wrap;
    }

    .scope-label {
      color: var(--text-secondary);
      font-size: 0.9rem;
      font-weight: 500;
    }

    .scope-pills {
      display: flex;
      gap: 0.35rem;
      background: var(--bg-secondary);
      padding: 0.25rem;
      border-radius: 12px;
      border: 1px solid var(--border-color);
    }

    .scope-pill {
      display: inline-flex;
      align-items: center;
      gap: 0.4rem;
      padding: 0.55rem 1rem;
      background: transparent;
      border: none;
      border-radius: 10px;
      color: var(--text-secondary);
      font-size: 0.875rem;
      font-weight: 500;
      font-family: inherit;
      cursor: pointer;
      transition: all 0.2s ease;

      mat-icon {
        font-size: 1.1rem;
        width: 1.1rem;
        height: 1.1rem;
      }

      &:hover:not(.active) {
        background: var(--bg-card-hover);
        color: var(--text-primary);
      }

      &.active {
        background: var(--accent-primary);
        color: var(--color-blue-1000);
        box-shadow: var(--shadow);

        mat-icon { color: var(--color-blue-1000); }
      }
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
      overflow-x: auto;
      border: 1px solid var(--border-color);
      border-radius: 10px;
      background: var(--bg-secondary);
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

    .key-events-scroll {
      max-height: 320px;
      overflow-y: auto;
      padding-right: 0.25rem;
    }

    .key-events-table .key-event-row {
      cursor: pointer;
      transition: background 0.15s ease;

      &:hover,
      &:focus-visible {
        background: var(--bg-card-hover);
        outline: none;
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

    .loading-state, .error-banner {
      display: flex;
      align-items: center;
      justify-content: center;
      gap: 0.75rem;
      padding: 2rem;
      color: var(--text-secondary);
    }

    .error-banner {
      justify-content: flex-start;
      margin-bottom: 1rem;
      padding: 0.75rem 1rem;
      border: 1px solid rgba(232, 111, 111, 0.4);
      border-radius: 8px;
      background: rgba(232, 111, 111, 0.08);
      color: #f4a5a5;
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
  private suggestionsService = inject(SuggestionsService);
  private snackBar = inject(MatSnackBar);

  stats = signal<DashboardStatsResponse | null>(null);
  loading = signal(false);
  error = signal<string | null>(null);
  scope = signal<DashboardScope>('all');
  autoRefresh = signal(true);
  keyEvents = signal<KeyEventSuggestion[]>([]);
  suggestionsGeneratedAt = signal<string | null>(null);

  metadataFields = [
    { key: 'camera_id', label: 'Camera ID' },
    { key: 'capture_type', label: 'Capture Type' },
    { key: 'location', label: 'Location' },
  ];

  private refreshSub?: Subscription;

  ngOnInit() {
    this.loadStats();
    this.loadKeyEvents();
    this.refreshSub = interval(30_000).subscribe(() => {
      if (this.autoRefresh()) {
        this.loadStats(true);
        this.loadKeyEvents(true);
      }
    });
  }

  ngOnDestroy() {
    this.refreshSub?.unsubscribe();
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
      this.error.set(null);
    }
    this.dashboardService.getStats(this.scope()).subscribe({
      next: (data) => {
        this.stats.set(data);
        this.loading.set(false);
      },
      error: (err) => {
        this.error.set(err?.error?.detail || err?.message || 'Failed to load dashboard');
        this.loading.set(false);
      },
    });
  }

  loadKeyEvents(silent = false) {
    this.suggestionsService.getSuggestions().subscribe({
      next: (data) => {
        this.keyEvents.set(data.key_events ?? []);
        this.suggestionsGeneratedAt.set(data.generated_at ?? null);
      },
      error: () => {
        if (!silent) {
          this.keyEvents.set([]);
        }
      },
    });
  }

  copyKeyEvent(ev: KeyEventSuggestion) {
    const text = ev.query_text?.trim();
    if (!text) return;
    navigator.clipboard.writeText(text).then(
      () => {
        this.snackBar.open('Search query copied', 'Close', { duration: 2500 });
      },
      () => {
        this.snackBar.open('Could not copy to clipboard', 'Close', { duration: 3000 });
      },
    );
  }

  formatEventTime(sec: number): string {
    if (!Number.isFinite(sec) || sec < 0) return '0:00';
    const m = Math.floor(sec / 60);
    const s = Math.floor(sec % 60);
    return `${m}:${s.toString().padStart(2, '0')}`;
  }

  kpiCards(data: DashboardStatsResponse) {
    const o = data.overview;
    return [
      { label: 'Total rows', value: o.total_rows, hint: 'All accessible VastDB rows' },
      { label: 'Segment rows', value: o.segment_rows, hint: 'Searchable clip segments' },
      { label: 'Unique videos', value: o.unique_videos, hint: 'Distinct original_video values' },
      { label: 'Video summaries', value: o.video_summary_rows, hint: 'Rollup rows' },
      { label: 'Public segments', value: o.public_segment_rows, hint: 'is_public=true' },
      { label: 'Private segments', value: o.private_segment_rows, hint: 'Restricted access' },
      {
        label: 'Duplicate slots',
        value: o.duplicate_segment_slots,
        hint: `${o.duplicate_segment_rows} extra rows from re-ingest`,
        warn: o.duplicate_segment_slots > 0,
      },
    ];
  }

  barWidth(day: UploadDayItem, all: UploadDayItem[]): number {
    const max = Math.max(...all.map(d => d.segment_rows), 1);
    return Math.max(4, (day.segment_rows / max) * 100);
  }

  shortDate(isoDate: string): string {
    const parts = isoDate.split('-');
    return parts.length === 3 ? `${parts[1]}/${parts[2]}` : isoDate;
  }

  formatTimestamp(value?: string | null): string {
    if (!value) return '—';
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return value;
    return date.toLocaleString();
  }

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
