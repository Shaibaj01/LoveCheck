"""
YOLO11 bbox JSON (one-shot segment).

Accepts either:
  - presigned HTTP(S) URL to MP4, or
  - base64-encoded MP4 in the JSON body

Run on the RTX GPU host:
  CUDA_VISIBLE_DEVICES=2 ./run.sh
"""

from __future__ import annotations

import asyncio
import base64
import binascii
import os
import re
import tempfile
import uuid
from collections import Counter
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import httpx
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field, HttpUrl, model_validator

YOLO_MODEL = os.environ.get("YOLO_MODEL", "yolo11s.pt")
YOLO_CONF = float(os.environ.get("YOLO_CONF", "0.4"))
YOLO_DEVICE = os.environ.get("YOLO_DEVICE", "0")
PERCEPTION_SOURCE = os.environ.get("PERCEPTION_SOURCE", "yolo11_coco")
DOWNLOAD_TIMEOUT_S = float(os.environ.get("DOWNLOAD_TIMEOUT_S", "120"))
MAX_DOWNLOAD_BYTES = int(os.environ.get("MAX_DOWNLOAD_BYTES", str(200 * 1024 * 1024)))
MAX_BASE64_CHARS = int(os.environ.get("MAX_BASE64_CHARS", str(280 * 1024 * 1024)))

_model = None
_DATA_URI_RE = re.compile(r"^data:video/[^;]+;base64,", re.IGNORECASE)


def _get_model():
    global _model
    if _model is None:
        from ultralytics import YOLO

        _model = YOLO(YOLO_MODEL)
    return _model


def _infer_video_sync(video_path: Path) -> list[dict[str, Any]]:
    import cv2

    model = _get_model()
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise RuntimeError(f"Cannot open video: {video_path}")
    vid_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    vid_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    cap.release()

    frames_out: list[dict[str, Any]] = []
    for i, result in enumerate(
        model.predict(
            source=str(video_path),
            stream=True,
            conf=YOLO_CONF,
            device=YOLO_DEVICE,
            verbose=False,
        )
    ):
        dets: list[dict[str, Any]] = []
        if result.boxes is not None:
            names = result.names or {}
            for box in result.boxes:
                x1, y1, x2, y2 = box.xyxy[0].tolist()
                cls_id = int(box.cls[0])
                dets.append(
                    {
                        "label": names.get(cls_id, str(cls_id)),
                        "confidence": round(float(box.conf[0]), 4),
                        "bbox": [int(x1), int(y1), int(x2), int(y2)],
                    }
                )
        frames_out.append(
            {
                "frame_index": i,
                "shape": [vid_h, vid_w],
                "detections": dets,
            }
        )
    return frames_out


def _aggregate_frames(frames: list[dict[str, Any]]) -> dict[str, Any]:
    class_counts: Counter[str] = Counter()
    max_conf = 0.0
    all_classes: set[str] = set()

    for frame in frames:
        for det in frame.get("detections", []):
            label = det.get("label") or "unknown"
            class_counts[label] += 1
            all_classes.add(label)
            conf = float(det.get("confidence") or 0.0)
            if conf > max_conf:
                max_conf = conf

    return {
        "object_classes": sorted(all_classes),
        "object_counts": dict(class_counts),
        "max_detection_conf": round(max_conf, 4),
        "frame_count": len(frames),
        "detection_count": sum(class_counts.values()),
    }


def _build_response(frames: list[dict[str, Any]], include_frames: bool) -> dict[str, Any]:
    summary = _aggregate_frames(frames)
    perception = {
        "source": PERCEPTION_SOURCE,
        "frames": frames if include_frames else None,
        **summary,
    }
    return {
        "ok": True,
        "perception_ok": len(frames) > 0,
        "perception_json": perception,
        "object_classes": summary["object_classes"],
        "object_counts": summary["object_counts"],
        "max_detection_conf": summary["max_detection_conf"],
        "frames": frames if include_frames else None,
    }


async def _download_video(url: str, dest: Path) -> None:
    async with httpx.AsyncClient(follow_redirects=True, timeout=DOWNLOAD_TIMEOUT_S) as client:
        async with client.stream("GET", url) as resp:
            if resp.status_code >= 400:
                body = await resp.aread()
                raise HTTPException(
                    502,
                    f"Presigned URL fetch failed: HTTP {resp.status_code} — {body[:200]!r}",
                )
            size = 0
            with dest.open("wb") as fh:
                async for chunk in resp.aiter_bytes(chunk_size=1024 * 1024):
                    size += len(chunk)
                    if size > MAX_DOWNLOAD_BYTES:
                        raise HTTPException(413, f"Download exceeds {MAX_DOWNLOAD_BYTES} bytes")
                    fh.write(chunk)


def _decode_video_base64(video_base64: str) -> bytes:
    raw = video_base64.strip()
    if len(raw) > MAX_BASE64_CHARS:
        raise HTTPException(413, f"video_base64 exceeds {MAX_BASE64_CHARS} characters")
    raw = _DATA_URI_RE.sub("", raw)
    try:
        data = base64.b64decode(raw, validate=True)
    except binascii.Error as exc:
        raise HTTPException(400, f"Invalid base64 in video_base64: {exc}") from exc
    if len(data) > MAX_DOWNLOAD_BYTES:
        raise HTTPException(413, f"Decoded video exceeds {MAX_DOWNLOAD_BYTES} bytes")
    if len(data) < 12:
        raise HTTPException(400, "Decoded video is too small to be a valid MP4")
    return data


def _tmp_video_path(tmp_dir: Path, filename: str | None) -> Path:
    suffix = Path(filename or "segment.mp4").suffix or ".mp4"
    if suffix.lower() not in (".mp4", ".mov", ".mkv", ".avi", ".webm"):
        suffix = ".mp4"
    return tmp_dir / f"{uuid.uuid4().hex}{suffix}"


@asynccontextmanager
async def lifespan(_app: FastAPI):
    await asyncio.to_thread(_get_model)
    yield


app = FastAPI(title="VSS YOLO11 Infer", version="1.1.0", lifespan=lifespan)


class InferRequest(BaseModel):
    url: HttpUrl | None = Field(
        None,
        description="Presigned HTTP/HTTPS URL to a segment MP4",
    )
    video_base64: str | None = Field(
        None,
        description="Base64-encoded MP4 bytes (optional data:video/mp4;base64, prefix)",
    )
    filename: str | None = Field(
        None,
        description="Optional hint when using video_base64 (e.g. segment.mp4)",
    )
    include_frames: bool = Field(
        False,
        description="If true, include per-frame bboxes in response (can be large)",
    )

    @model_validator(mode="after")
    def _exactly_one_input(self) -> InferRequest:
        has_url = self.url is not None
        has_b64 = bool(self.video_base64 and self.video_base64.strip())
        if has_url == has_b64:
            raise ValueError("Provide exactly one of: url, video_base64")
        return self


@app.get("/healthz")
async def healthz() -> dict[str, Any]:
    cuda_ok = False
    try:
        import torch

        cuda_ok = torch.cuda.is_available()
    except ImportError:
        pass
    return {
        "ok": True,
        "model": YOLO_MODEL,
        "device": YOLO_DEVICE,
        "cuda_available": cuda_ok,
        "model_loaded": _model is not None,
        "inputs": ["url", "video_base64"],
    }


async def _run_infer_on_path(video_path: Path, include_frames: bool) -> dict[str, Any]:
    try:
        frames = await asyncio.to_thread(_infer_video_sync, video_path)
    except Exception as exc:
        raise HTTPException(502, f"Inference failed: {exc}") from exc
    return _build_response(frames, include_frames)


@app.post("/v1/infer")
async def infer(req: InferRequest) -> dict[str, Any]:
    tmp_dir = Path(tempfile.gettempdir()) / "vss-yolo-infer"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    video_path = _tmp_video_path(tmp_dir, req.filename)

    try:
        if req.url is not None:
            url = str(req.url)
            scheme = urlparse(url).scheme.lower()
            if scheme not in ("http", "https"):
                raise HTTPException(400, f"Unsupported URL scheme: {scheme}")
            await _download_video(url, video_path)
        else:
            data = _decode_video_base64(req.video_base64 or "")
            video_path.write_bytes(data)

        return await _run_infer_on_path(video_path, req.include_frames)
    except HTTPException:
        raise
    finally:
        video_path.unlink(missing_ok=True)


@app.post("/v1/infer-base64")
async def infer_base64(req: InferRequest) -> dict[str, Any]:
    """Alias when clients always send base64 (url must be omitted)."""
    if not req.video_base64:
        raise HTTPException(400, "video_base64 is required for /v1/infer-base64")
    if req.url is not None:
        raise HTTPException(400, "Use /v1/infer with url only, not both")
    return await infer(req)
