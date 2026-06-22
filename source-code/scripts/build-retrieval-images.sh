#!/usr/bin/env bash
# Build and push retrieval / edge Docker images (backend, frontend, streaming, batch-sync).
#
# Backend, streaming, and batch-sync use source-code/ as build context so Docker can
# COPY shared/ingest_metadata.py. Frontend builds from retrieval/video-frontend/.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ECR="${ECR:-110450271409.dkr.ecr.eu-west-1.amazonaws.com/dev/solutions}"
TAG="${TAG:-v2}"

build_from_source_code() {
  local dockerfile="$1"
  local image="$2"
  echo "==> $image ($dockerfile)"
  docker buildx build \
    -f "$ROOT/$dockerfile" \
    -t "$ECR/$image:$TAG" \
    --push \
    "$ROOT"
}

build_from_service_dir() {
  local dir="$1"
  local image="$2"
  echo "==> $image ($dir)"
  docker buildx build \
    -t "$ECR/$image:$TAG" \
    --push \
    "$ROOT/$dir"
}

build_from_source_code retrieval/video-backend/Dockerfile  vss-video-backend
build_from_source_code video-streaming/Dockerfile        vss-video-streaming
build_from_source_code video-batch-sync/Dockerfile       vss-video-batch-sync
build_from_service_dir retrieval/video-frontend            vss-video-frontend

echo "Done. Pushed retrieval images (tag=$TAG) to $ECR"
