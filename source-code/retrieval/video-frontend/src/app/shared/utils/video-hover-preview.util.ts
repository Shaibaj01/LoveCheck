/** Play a muted hover preview; loads `url` lazily and waits for canplay. */
let activeHoverPreview: HTMLVideoElement | null = null;

export function claimHoverPreview(video: HTMLVideoElement): void {
  if (activeHoverPreview && activeHoverPreview !== video) {
    stopHoverPreview(activeHoverPreview);
  }
  activeHoverPreview = video;
}

export function releaseHoverPreview(video: HTMLVideoElement): void {
  if (activeHoverPreview === video) {
    activeHoverPreview = null;
  }
}

export function ensureVideoMuted(video: HTMLVideoElement): void {
  video.muted = true;
  video.defaultMuted = true;
  video.volume = 0;
}

export async function playVideoMuted(video: HTMLVideoElement): Promise<void> {
  ensureVideoMuted(video);
  await video.play();
}

/** Seek then wait until the target position is buffered enough to play. */
export function seekVideoAndWait(
  video: HTMLVideoElement,
  sec: number,
): Promise<void> {
  return new Promise((resolve) => {
    if (sec <= 0.05 || Math.abs(video.currentTime - sec) < 0.1) {
      resolve();
      return;
    }

    let settled = false;
    const finish = () => {
      if (settled) return;
      settled = true;
      cleanup();
      resolve();
    };

    const cleanup = () => {
      video.removeEventListener('seeked', onSeeked);
      video.removeEventListener('canplay', onCanPlay);
    };

    const onCanPlay = () => finish();

    const onSeeked = () => {
      if (video.readyState >= HTMLMediaElement.HAVE_FUTURE_DATA) {
        finish();
      } else {
        video.addEventListener('canplay', onCanPlay, { once: true });
      }
    };

    video.addEventListener('seeked', onSeeked, { once: true });
    video.currentTime = sec;
  });
}

export function playHoverPreview(
  video: HTMLVideoElement,
  url: string,
  options?: { seekSec?: number; signal?: AbortSignal },
): Promise<boolean> {
  return new Promise((resolve) => {
    if (!url || options?.signal?.aborted) {
      resolve(false);
      return;
    }

    let settled = false;
    const finish = (ok: boolean) => {
      if (settled) return;
      settled = true;
      cleanup();
      resolve(ok);
    };

    const cleanup = () => {
      video.removeEventListener('canplay', onReady);
      video.removeEventListener('loadeddata', onReady);
      video.removeEventListener('error', onError);
      options?.signal?.removeEventListener('abort', onAbort);
    };

    const onAbort = () => finish(false);

    const tryPlay = async () => {
      if (options?.signal?.aborted) {
        finish(false);
        return;
      }
      try {
        ensureVideoMuted(video);
        if (options?.seekSec != null && options.seekSec > 0) {
          video.currentTime = options.seekSec;
        }
        await video.play();
        finish(true);
      } catch {
        finish(false);
      }
    };

    const onReady = () => {
      void tryPlay();
    };

    const onError = () => finish(false);

    options?.signal?.addEventListener('abort', onAbort, { once: true });
    video.addEventListener('error', onError, { once: true });
    ensureVideoMuted(video);

    const alreadyHasSource =
      !!video.currentSrc &&
      (video.currentSrc === url || video.dataset['previewUrl'] === url);
    if (!alreadyHasSource) {
      video.dataset['previewUrl'] = url;
      video.src = url;
      video.load();
    } else if (!video.dataset['previewUrl']) {
      video.dataset['previewUrl'] = url;
    }

    if (video.readyState >= HTMLMediaElement.HAVE_FUTURE_DATA) {
      void tryPlay();
      return;
    }

    video.addEventListener('canplay', onReady, { once: true });
    video.addEventListener('loadeddata', onReady, { once: true });
  });
}

export function stopHoverPreview(video: HTMLVideoElement, resetTime = true): void {
  video.pause();
  if (resetTime) {
    video.currentTime = 0;
  }
}
