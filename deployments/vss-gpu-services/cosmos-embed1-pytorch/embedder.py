"""
Cosmos-Embed1 functionality: model load, frame sampling, and embedding.

This module owns everything the amd64-only NIM used to hide internally:
MP4 decode, 8-frame sampling, image->frames tiling, text tokenization, and the
actual `get_video_embeddings` / `get_text_embeddings` calls.

`sample_frames()` is the SINGLE source of truth for frame selection so ingest and
query use identical preprocessing and stay in the same vector space.
"""
import io
import logging
import os
import time
from typing import List

import av
import numpy as np
import torch
from PIL import Image
from transformers import AutoModel, AutoProcessor

logger = logging.getLogger("cosmos-embed1.embedder")

# --- Config (env-overridable) ------------------------------------------------
MODEL_ID = os.getenv("COSMOS_MODEL_ID", "nvidia/Cosmos-Embed1-224p")
NUM_FRAMES = int(os.getenv("COSMOS_NUM_FRAMES", "8"))   # model constraint: trained on 8
EMBED_DIM = int(os.getenv("COSMOS_EMBED_DIM", "256"))
DEVICE = os.getenv("COSMOS_DEVICE", "cuda")
DTYPE = torch.bfloat16

_model = None
_processor = None


def load_model() -> None:
    global _model, _processor
    if _model is not None:
        return
    logger.info(f"Loading {MODEL_ID} on {DEVICE} ({DTYPE})...")
    t0 = time.time()
    _model = AutoModel.from_pretrained(MODEL_ID, trust_remote_code=True).to(DEVICE, dtype=DTYPE).eval()
    _processor = AutoProcessor.from_pretrained(MODEL_ID, trust_remote_code=True)
    logger.info(f"Model ready in {time.time() - t0:.1f}s")


# --- Preprocessing -----------------------------------------------------------
def sample_frames(frames: np.ndarray, n: int = NUM_FRAMES) -> np.ndarray:
    """Uniformly sample exactly `n` frames from a decoded clip (T, H, W, 3).

    Shorter clips are padded by repeating the last frame. This is the one policy
    used everywhere (ingest video + image tiling) so ingest/query can't drift.
    """
    t = frames.shape[0]
    if t == 0:
        raise ValueError("no frames decoded")
    if t >= n:
        idx = np.linspace(0, t - 1, num=n).round().astype(int)
    else:
        idx = np.concatenate([np.arange(t), np.full(n - t, t - 1)])
    return frames[idx]


def decode_mp4(video_bytes: bytes) -> np.ndarray:
    """Decode an MP4 (any container PyAV supports) to (T, H, W, 3) uint8 RGB."""
    container = av.open(io.BytesIO(video_bytes))
    frames = [f.to_ndarray(format="rgb24") for f in container.decode(video=0)]
    container.close()
    if not frames:
        raise ValueError("no video frames in input")
    return np.stack(frames)


def image_to_frames(image_bytes: bytes, n: int = NUM_FRAMES) -> np.ndarray:
    """A single image becomes an n-frame clip (Cosmos-Embed1 has no image path)."""
    img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    arr = np.asarray(img)  # (H, W, 3)
    return np.repeat(arr[None, ...], n, axis=0)


# --- Embedding ---------------------------------------------------------------
def _extract(out) -> torch.Tensor:
    """Pull the projected embedding tensor from the model output across variants."""
    for attr in ("visual_proj", "text_proj", "visual_embeddings", "text_embeddings", "embeddings"):
        if hasattr(out, attr):
            return getattr(out, attr)
    if isinstance(out, dict):
        for k in ("visual_proj", "text_proj", "visual_embeddings", "text_embeddings", "embeddings"):
            if k in out:
                return out[k]
    if isinstance(out, torch.Tensor):
        return out
    raise RuntimeError(f"cannot locate embedding tensor in model output: {type(out)}")


def _finalize(vecs: torch.Tensor) -> List[List[float]]:
    vecs = torch.nn.functional.normalize(vecs.float(), dim=-1)
    return vecs.cpu().tolist()


@torch.inference_mode()
def embed_videos(clips: List[np.ndarray]) -> List[List[float]]:
    """Embed a batch of decoded clips. Each clip is sampled to NUM_FRAMES first."""
    batch = np.stack([sample_frames(c) for c in clips])  # (B, n, H, W, 3)
    # Cosmos-Embed1 processor requires channel-first BTCHW; frames decode as
    # channel-last (H, W, 3), so permute or the model reads H as the channel axis.
    batch = np.ascontiguousarray(batch.transpose(0, 1, 4, 2, 3))  # -> (B, n, 3, H, W)
    inputs = _processor(videos=batch).to(DEVICE, dtype=DTYPE)
    out = _model.get_video_embeddings(**inputs)
    return _finalize(_extract(out))


@torch.inference_mode()
def embed_texts(texts: List[str]) -> List[List[float]]:
    inputs = _processor(text=texts).to(DEVICE, dtype=DTYPE)
    out = _model.get_text_embeddings(**inputs)
    return _finalize(_extract(out))
