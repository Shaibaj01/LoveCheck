import logging
import os
import tempfile
from typing import List, Optional

try:
    import cv2

    CV2_AVAILABLE = True
except ImportError:
    CV2_AVAILABLE = False


def extract_frames_from_video(
    video_bytes: bytes,
    num_frames: int = 3,
    frame_interval: Optional[float] = None,
) -> List[bytes]:
    """Extract PNG frame bytes from a video segment."""
    if not CV2_AVAILABLE:
        raise ImportError("opencv-python is required for visual embeddings")

    with tempfile.NamedTemporaryFile(delete=False, suffix=".mp4") as tmp_file:
        tmp_file.write(video_bytes)
        tmp_path = tmp_file.name

    try:
        cap = cv2.VideoCapture(tmp_path)
        if not cap.isOpened():
            raise ValueError("Could not open segment video")

        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
        duration = total_frames / fps if total_frames > 0 else 0
        if total_frames == 0:
            raise ValueError("Segment video has no frames")

        if num_frames == 1:
            frame_indices = [0]
        elif frame_interval is not None:
            frame_indices = []
            current_time = 0.0
            while current_time < duration and len(frame_indices) < num_frames:
                frame_idx = int(current_time * fps)
                if frame_idx < total_frames:
                    frame_indices.append(frame_idx)
                current_time += frame_interval
        else:
            if num_frames >= total_frames:
                frame_indices = list(range(total_frames))
            else:
                step = total_frames / num_frames
                frame_indices = [int(i * step) for i in range(num_frames)]

        frames: List[bytes] = []
        for frame_idx in frame_indices:
            cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
            ret, frame = cap.read()
            if ret and frame is not None:
                _, buffer = cv2.imencode(".png", frame)
                frames.append(buffer.tobytes())

        cap.release()
        if not frames:
            raise ValueError("Could not extract frames from segment video")
        logging.info(f"[FRAMES] Extracted {len(frames)} frames from segment")
        return frames
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
