import { Component, EventEmitter, Input, Output } from '@angular/core';
import { CommonModule } from '@angular/common';
import { MatIconModule } from '@angular/material/icon';

export type VideoScope = 'all' | 'mine' | 'public';

@Component({
  selector: 'app-scope-pills',
  standalone: true,
  imports: [CommonModule, MatIconModule],
  template: `
    <div class="scope-filter">
      <label class="scope-label">{{ label }}</label>
      <div class="scope-pills">
        <button
          type="button"
          class="scope-pill"
          [class.active]="scope === 'all'"
          (click)="select('all')">
          <mat-icon>public</mat-icon>
          <span>All Videos</span>
        </button>
        <button
          type="button"
          class="scope-pill"
          [class.active]="scope === 'mine'"
          (click)="select('mine')">
          <mat-icon>person</mat-icon>
          <span>My Videos</span>
        </button>
        <button
          type="button"
          class="scope-pill"
          [class.active]="scope === 'public'"
          (click)="select('public')">
          <mat-icon>visibility</mat-icon>
          <span>Public Only</span>
        </button>
      </div>
    </div>
  `,
  styles: [`
    .scope-filter {
      display: flex;
      align-items: center;
      gap: 1rem;
      flex-wrap: wrap;
    }

    .scope-label {
      color: var(--text-secondary);
      font-size: 0.95rem;
      font-weight: 500;
      white-space: nowrap;
    }

    .scope-pills {
      display: flex;
      gap: 0.5rem;
      background: var(--bg-secondary);
      padding: 0.25rem;
      border-radius: 12px;
      border: 1px solid var(--border-color);
      transition: background 0.3s ease, border-color 0.3s ease;
    }

    .scope-pill {
      display: flex;
      align-items: center;
      gap: 0.5rem;
      padding: 0.625rem 1.25rem;
      background: transparent;
      border: none;
      border-radius: 10px;
      color: var(--text-secondary);
      font-size: 0.9rem;
      font-weight: 500;
      font-family: 'Roboto', sans-serif;
      cursor: pointer;
      transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);

      * {
        cursor: pointer;
      }

      mat-icon,
      span {
        font-size: 1.25rem;
        width: 1.25rem;
        height: 1.25rem;
        cursor: pointer;
        pointer-events: none;
      }

      span {
        width: auto;
        height: auto;
        font-size: 0.9rem;
      }

      &:hover:not(.active) {
        background: var(--bg-card-hover);
        color: var(--text-primary);
        transform: translateY(-1px);
      }

      &.active {
        background: var(--color-lightblue-400);
        color: var(--color-blue-1000);
        box-shadow: var(--shadow);
        transform: translateY(0);

        mat-icon {
          color: var(--color-blue-1000);
        }
      }

      &:active {
        transform: translateY(1px);
      }
    }
  `],
})
export class ScopePillsComponent {
  @Input() label = 'Search in:';
  @Input() scope: VideoScope = 'all';
  @Output() scopeChange = new EventEmitter<VideoScope>();

  select(next: VideoScope) {
    if (next !== this.scope) {
      this.scopeChange.emit(next);
    }
  }
}
