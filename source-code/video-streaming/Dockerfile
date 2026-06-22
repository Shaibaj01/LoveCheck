# Video Stream Capture Dockerfile
#
# Build from source-code/ (not this directory):
#   cd source-code
#   docker buildx build -f video-streaming/Dockerfile -t your.registry/vss-video-streaming:v2 --push .
FROM python:3.10-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    wget \
    curl \
    nodejs \
    && rm -rf /var/lib/apt/lists/* \
    && node --version

WORKDIR /app

COPY video-streaming/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install --no-cache-dir yt-dlp

COPY shared/ingest_metadata.py ./ingest_metadata.py
COPY video-streaming/src/web_service.py ./web_service.py

RUN mkdir -p recordings
RUN chmod +x web_service.py

ENV PYTHONUNBUFFERED=1

CMD ["python", "web_service.py"]
