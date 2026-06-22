import {
  Component,
  Input,
  OnDestroy,
  OnInit,
  computed,
  inject,
  signal,
} from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormGroup, ReactiveFormsModule } from '@angular/forms';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatSelectModule } from '@angular/material/select';
import { MatIconModule } from '@angular/material/icon';
import { Subscription } from 'rxjs';
import { IngestMetadataService } from '../services/ingest-metadata.service';
import { IngestMetadataFieldSet } from '../models/ingest-metadata.model';

@Component({
  selector: 'app-ingest-metadata-fields',
  standalone: true,
  imports: [
    CommonModule,
    ReactiveFormsModule,
    MatFormFieldModule,
    MatInputModule,
    MatSelectModule,
    MatIconModule,
  ],
  template: `
    <div [formGroup]="form" [class.material-variant]="variant === 'material'">
    @if (metadataService.loading() && !cfg()) {
      <p class="metadata-loading">Loading metadata options…</p>
    } @else if (metadataService.loadError()) {
      <p class="metadata-error">{{ metadataService.loadError() }}</p>
    } @else if (cfg()) {
      @if (showSectionTitle && showsLocation()) {
        <h3 class="section-title">
          <mat-icon>info</mat-icon>
          <span>{{ cfg()!.labels['metadata_section_title'] }}</span>
        </h3>
        @if (cfg()!.labels['metadata_section_description']) {
          <p class="section-description">{{ cfg()!.labels['metadata_section_description'] }}</p>
        }
      }

      @if (showsLocation()) {
        @if (variant === 'material') {
          <mat-form-field appearance="outline">
            <mat-label>{{ cfg()!.labels['camera_id'] }}</mat-label>
            <input matInput formControlName="camera_id" [placeholder]="cfg()!.placeholders['camera_id']">
            <mat-icon matSuffix>videocam</mat-icon>
          </mat-form-field>

          <mat-form-field appearance="outline">
            <mat-label>{{ cfg()!.labels['capture_type'] }}</mat-label>
            <mat-select formControlName="capture_type">
              <mat-option [value]="">{{ cfg()!.capture_type_default_label }}</mat-option>
              @for (opt of cfg()!.capture_types; track opt.value) {
                <mat-option [value]="opt.value">{{ opt.label }}</mat-option>
              }
            </mat-select>
            <mat-icon matSuffix>category</mat-icon>
          </mat-form-field>

          <mat-form-field appearance="outline">
            <mat-label>{{ cfg()!.labels['location'] }}</mat-label>
            <input matInput formControlName="location" [placeholder]="cfg()!.placeholders['location']">
            <mat-icon matSuffix>location_on</mat-icon>
          </mat-form-field>
        } @else {
          <div class="form-field-wrapper">
            <label class="field-label">{{ cfg()!.labels['camera_id'] }}</label>
            <input type="text" class="custom-input" formControlName="camera_id" [placeholder]="cfg()!.placeholders['camera_id']">
          </div>

          <div class="form-field-wrapper">
            <label class="field-label">{{ cfg()!.labels['capture_type'] }}</label>
            <select class="custom-input" formControlName="capture_type">
              <option value="">{{ cfg()!.capture_type_default_label }}</option>
              @for (opt of cfg()!.capture_types; track opt.value) {
                <option [value]="opt.value">{{ opt.label }}</option>
              }
            </select>
          </div>

          <div class="form-field-wrapper">
            <label class="field-label">{{ cfg()!.labels['location'] }}</label>
            <input type="text" class="custom-input" formControlName="location" [placeholder]="cfg()!.placeholders['location']">
          </div>
        }
      }

      @if (showsAnalysis()) {
        @if (variant === 'material') {
          <mat-form-field appearance="outline">
            <mat-label>Analysis Scenario</mat-label>
            <mat-select formControlName="scenario">
              <mat-option [value]="">{{ cfg()!.analysis_scenario_default_label }}</mat-option>
              @for (opt of cfg()!.analysis_scenarios; track opt.value) {
                <mat-option [value]="opt.value">{{ opt.label }}</mat-option>
              }
            </mat-select>
            <mat-icon matSuffix>psychology</mat-icon>
            <mat-hint>Select the analysis prompt scenario for this video</mat-hint>
          </mat-form-field>
        } @else {
          <div class="form-field-wrapper">
            <label class="field-label">Analysis Scenario</label>
            <select class="custom-input" formControlName="scenario">
              <option value="">{{ cfg()!.analysis_scenario_default_label }}</option>
              @for (opt of cfg()!.analysis_scenarios; track opt.value) {
                <option [value]="opt.value">{{ opt.label }}</option>
              }
            </select>
            <span class="field-hint">Select the analysis prompt scenario for this video</span>
          </div>
        }

        <div class="custom-prompt-toggle">
          <label class="toggle-wrapper">
            <input type="checkbox" formControlName="useCustomPrompt" class="toggle-checkbox">
            <span class="toggle-label">{{ cfg()!.labels['use_custom_prompt'] }}</span>
          </label>
        </div>

        @if (useCustomPrompt()) {
          @if (variant === 'material') {
            <mat-form-field appearance="outline" class="custom-prompt-field">
              <mat-label>Custom Prompt</mat-label>
              <textarea matInput formControlName="custom_prompt"
                        [placeholder]="cfg()!.placeholders['custom_prompt']"
                        rows="4"
                        [maxlength]="cfg()!.custom_prompt_max_length"></textarea>
              <mat-icon matSuffix>edit_note</mat-icon>
              <mat-hint align="end">{{ customPromptLength() }}/{{ cfg()!.custom_prompt_max_length }}</mat-hint>
            </mat-form-field>
          } @else {
            <div class="form-field-wrapper custom-prompt-wrapper">
              <label class="field-label">Custom Prompt</label>
              <textarea class="custom-input custom-prompt-textarea"
                        formControlName="custom_prompt"
                        [placeholder]="cfg()!.placeholders['custom_prompt']"
                        rows="4"
                        [maxlength]="cfg()!.custom_prompt_max_length"></textarea>
              <span class="field-hint">
                {{ customPromptLength() }}/{{ cfg()!.custom_prompt_max_length }} characters.
              </span>
            </div>
          }
        }
      }
    }
    </div>
  `,
  styles: [`
    .metadata-loading, .metadata-error {
      font-size: 13px;
      color: var(--text-muted);
      margin: 8px 0;
    }
    .metadata-error { color: var(--warn-color, #c62828); }
    .section-title {
      display: flex;
      align-items: center;
      gap: 8px;
      margin: 16px 0 8px;
      font-size: 15px;
      font-weight: 600;
    }
    .section-description {
      margin: 0 0 12px;
      font-size: 13px;
      color: var(--text-muted);
    }
    .custom-prompt-toggle { margin: 8px 0 12px; }
    .toggle-wrapper {
      display: flex;
      align-items: center;
      gap: 8px;
      cursor: pointer;

      .toggle-label {
        color: var(--text-primary);
        font-size: 0.95rem;
      }
    }

    .form-field-wrapper {
      margin-bottom: 1.5rem;

      .field-label {
        display: block;
        color: var(--text-primary);
        font-size: 0.875rem;
        font-weight: 500;
        margin-bottom: 0.5rem;
        letter-spacing: 0.3px;
      }

      .custom-input {
        width: 100%;
        padding: 0.875rem 1rem;
        background: var(--bg-secondary);
        border: 1px solid var(--border-color);
        border-radius: 12px;
        color: var(--text-primary);
        font-size: 0.95rem;
        outline: none;
        transition: all 0.3s ease;
        font-family: inherit;
        box-sizing: border-box;

        &::placeholder {
          color: var(--text-muted);
        }

        &:hover {
          border-color: var(--border-hover);
          background: var(--bg-card-hover);
        }

        &:focus {
          border-color: var(--accent-primary);
          background: var(--bg-card-hover);
          box-shadow: 0 0 0 3px rgba(0, 217, 255, 0.1);
        }

        option {
          background: var(--bg-card);
          color: var(--text-primary);
        }
      }

      select.custom-input {
        cursor: pointer;
        appearance: none;
        background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='8' viewBox='0 0 12 8'%3E%3Cpath fill='%23e8ebec' d='M1.41 0 6 4.58 10.59 0 12 1.41l-6 6-6-6z'/%3E%3C/svg%3E");
        background-repeat: no-repeat;
        background-position: right 1rem center;
        padding-right: 2.5rem;
      }

      .custom-prompt-textarea {
        min-height: 5rem;
        resize: vertical;
      }

      .field-hint {
        display: block;
        margin-top: 0.375rem;
        font-size: 0.75rem;
        color: var(--text-primary);
        opacity: 0.85;
        font-style: italic;
      }
    }

    .custom-prompt-field { width: 100%; }

    .material-variant ::ng-deep .mat-mdc-form-field {
      width: 100%;
      display: block;
      margin-bottom: 1rem;

      .mat-mdc-text-field-wrapper {
        background: var(--bg-secondary) !important;
        border-radius: 12px !important;
      }

      .mat-mdc-form-field-flex {
        background: var(--bg-secondary) !important;
      }

      .mdc-notched-outline__leading,
      .mdc-notched-outline__notch,
      .mdc-notched-outline__trailing {
        border-color: var(--border-color) !important;
      }

      &:hover .mdc-notched-outline__leading,
      &:hover .mdc-notched-outline__notch,
      &:hover .mdc-notched-outline__trailing {
        border-color: var(--border-hover) !important;
      }

      &.mat-focused .mdc-notched-outline__leading,
      &.mat-focused .mdc-notched-outline__notch,
      &.mat-focused .mdc-notched-outline__trailing {
        border-color: var(--accent-primary) !important;
      }

      .mat-mdc-input-element,
      .mat-mdc-select-value,
      .mat-mdc-select-value-text {
        color: var(--text-primary) !important;
      }

      .mat-mdc-floating-label,
      .mat-mdc-form-field-label {
        color: var(--text-secondary) !important;
      }

      &.mat-focused .mat-mdc-floating-label {
        color: var(--accent-primary) !important;
      }

      .mat-mdc-select-arrow,
      .mat-icon {
        color: var(--accent-primary) !important;
      }

      input::placeholder,
      textarea::placeholder {
        color: var(--text-muted) !important;
      }

      .mat-mdc-form-field-hint {
        color: var(--text-muted) !important;
      }
    }
  `],
})
export class IngestMetadataFieldsComponent implements OnInit, OnDestroy {
  @Input({ required: true }) form!: FormGroup;
  @Input() variant: 'material' | 'native' = 'material';
  @Input() fields: IngestMetadataFieldSet = 'all';
  @Input() showSectionTitle = true;

  readonly metadataService = inject(IngestMetadataService);
  readonly cfg = computed(() => this.metadataService.config());
  private toggleSub?: Subscription;

  ngOnInit(): void {
    void this.metadataService.ensureLoaded();
    if (!this.showsAnalysis()) {
      return;
    }
    this.useCustomPrompt.set(this.form.get('useCustomPrompt')?.value === true);
    this.syncScenarioDisabled(this.form.get('useCustomPrompt')?.value === true);
    this.toggleSub = this.form.get('useCustomPrompt')?.valueChanges.subscribe((useCustom) => {
      this.syncScenarioDisabled(!!useCustom);
    });
  }

  ngOnDestroy(): void {
    this.toggleSub?.unsubscribe();
  }

  showsLocation(): boolean {
    return this.fields === 'all' || this.fields === 'location';
  }

  showsAnalysis(): boolean {
    return this.fields === 'all' || this.fields === 'analysis';
  }

  useCustomPrompt = signal(false);

  customPromptLength(): number {
    return this.form.get('custom_prompt')?.value?.length || 0;
  }

  private syncScenarioDisabled(useCustom: boolean): void {
    this.useCustomPrompt.set(useCustom);
    const scenario = this.form.get('scenario');
    if (!scenario) {
      return;
    }
    if (useCustom) {
      scenario.disable({ emitEvent: false });
    } else {
      scenario.enable({ emitEvent: false });
    }
  }
}
