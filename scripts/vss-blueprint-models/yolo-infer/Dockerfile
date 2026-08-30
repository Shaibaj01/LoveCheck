# YOLO11 presigned-infer runtime (CUDA 13).
# Build: docker build -t yolo-infer:latest .
# deploy.sh bind-mounts this directory over /app at runtime.
FROM python:3.12-slim

# opencv/ffmpeg runtime libs for video decoding
RUN apt-get update && apt-get install -y --no-install-recommends \
      libglib2.0-0 libgl1 ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# torch/torchvision for CUDA 13 (GB200/Blackwell) — pinned to the host-proven build
RUN pip install --no-cache-dir \
      --index-url https://download.pytorch.org/whl/cu130 \
      torch==2.12.1 torchvision==0.27.1

# application deps (torch already satisfied above so it is not re-pulled from PyPI)
RUN pip install --no-cache-dir \
      ultralytics==8.4.89 \
      fastapi==0.139.0 \
      "uvicorn[standard]==0.50.1" \
      httpx==0.28.1 \
      pydantic==2.13.4 \
      opencv-python-headless

ENV YOLO_MODEL=yolo11s.pt \
    YOLO_DEVICE=0 \
    YOLO_CONF=0.4 \
    YOLO_CONFIG_DIR=/tmp/Ultralytics

WORKDIR /app
COPY main.py .
EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
