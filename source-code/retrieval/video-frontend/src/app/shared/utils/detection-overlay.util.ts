export interface DetectionBox {
  label: string;
  confidence: number;
  bbox: [number, number, number, number];
}

export interface DetectionFrame {
  frame_index: number;
  time_sec: number;
  shape?: number[];
  detections: DetectionBox[];
}

export interface DetectionSidecar {
  source?: string;
  segment_source?: string;
  video_shape?: number[];
  fps?: number;
  frames?: DetectionFrame[];
}

export const DETECTION_OVERLAY_STORAGE_KEY = 'vss_detection_overlay';

export function readDetectionOverlayPref(): boolean {
  try {
    return localStorage.getItem(DETECTION_OVERLAY_STORAGE_KEY) === '1';
  } catch {
    return false;
  }
}

export function writeDetectionOverlayPref(enabled: boolean): void {
  try {
    localStorage.setItem(DETECTION_OVERLAY_STORAGE_KEY, enabled ? '1' : '0');
  } catch {
    // ignore storage errors
  }
}

export function findFrameForTime(frames: DetectionFrame[], timeSec: number): DetectionFrame | null {
  if (!frames?.length) return null;
  let best = frames[0];
  let bestDelta = Math.abs((best.time_sec ?? 0) - timeSec);
  for (const frame of frames) {
    const delta = Math.abs((frame.time_sec ?? 0) - timeSec);
    if (delta < bestDelta) {
      best = frame;
      bestDelta = delta;
    }
  }
  return bestDelta <= 0.35 ? best : null;
}

/** Map native bbox coords → displayed pixels accounting for object-fit: contain letterboxing. */
export function videoContentLayout(video: HTMLVideoElement): {
  offsetX: number;
  offsetY: number;
  scale: number;
  srcW: number;
  srcH: number;
  displayW: number;
  displayH: number;
} | null {
  const displayW = video.clientWidth;
  const displayH = video.clientHeight;
  const srcW = video.videoWidth;
  const srcH = video.videoHeight;
  if (!displayW || !displayH || !srcW || !srcH) return null;

  const scale = Math.min(displayW / srcW, displayH / srcH);
  const contentW = srcW * scale;
  const contentH = srcH * scale;
  return {
    offsetX: (displayW - contentW) / 2,
    offsetY: (displayH - contentH) / 2,
    scale,
    srcW,
    srcH,
    displayW,
    displayH,
  };
}

function bboxSourceSize(frame: DetectionFrame | null, layout: NonNullable<ReturnType<typeof videoContentLayout>>) {
  const shape = frame?.shape;
  if (Array.isArray(shape) && shape.length >= 2) {
    const h = Number(shape[0]);
    const w = Number(shape[1]);
    if (h > 0 && w > 0) {
      return { srcW: w, srcH: h };
    }
  }
  return { srcW: layout.srcW, srcH: layout.srcH };
}

export function syncOverlayCanvasSize(canvas: HTMLCanvasElement, video: HTMLVideoElement): void {
  const layout = videoContentLayout(video);
  if (!layout) return;
  canvas.width = Math.max(1, Math.round(layout.displayW));
  canvas.height = Math.max(1, Math.round(layout.displayH));
  canvas.style.width = `${layout.displayW}px`;
  canvas.style.height = `${layout.displayH}px`;
}

export function drawDetectionOverlay(
  canvas: HTMLCanvasElement,
  video: HTMLVideoElement,
  frame: DetectionFrame | null,
): void {
  const ctx = canvas.getContext('2d');
  if (!ctx) return;

  syncOverlayCanvasSize(canvas, video);
  ctx.clearRect(0, 0, canvas.width, canvas.height);
  if (!frame?.detections?.length) return;

  const layout = videoContentLayout(video);
  if (!layout) return;

  const { srcW, srcH } = bboxSourceSize(frame, layout);
  const scale = Math.min(layout.displayW / srcW, layout.displayH / srcH);
  const offsetX = (layout.displayW - srcW * scale) / 2;
  const offsetY = (layout.displayH - srcH * scale) / 2;

  for (const det of frame.detections) {
    const bbox = det.bbox;
    if (!bbox || bbox.length < 4) continue;
    const [x1, y1, x2, y2] = bbox;
    const left = offsetX + x1 * scale;
    const top = offsetY + y1 * scale;
    const width = Math.max(1, (x2 - x1) * scale);
    const height = Math.max(1, (y2 - y1) * scale);

    ctx.strokeStyle = 'rgba(34, 197, 94, 0.95)';
    ctx.lineWidth = 2;
    ctx.strokeRect(left, top, width, height);

    const label = `${det.label}${det.confidence ? ` ${Math.round(det.confidence * 100)}%` : ''}`;
    ctx.font = '12px sans-serif';
    const textW = ctx.measureText(label).width + 8;
    ctx.fillStyle = 'rgba(34, 197, 94, 0.9)';
    ctx.fillRect(left, Math.max(0, top - 18), textW, 18);
    ctx.fillStyle = '#041008';
    ctx.fillText(label, left + 4, Math.max(12, top - 5));
  }
}
