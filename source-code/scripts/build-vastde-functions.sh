#!/usr/bin/env bash
# Build and push DataEngine (vastde) pipeline function images.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ECR="${ECR:-110450271409.dkr.ecr.eu-west-1.amazonaws.com/dev/solutions}"
TAG="${TAG:-v2}"

build_and_push() {
  local dir="$1"
  local func_name="$2"
  local image_name="${3:-$func_name}"

  echo "==> $func_name ($dir)"
  cd "$ROOT/$dir"
  vastde functions build "$func_name"
  docker tag "$func_name" "$ECR/$image_name:$TAG"
  docker push "$ECR/$image_name:$TAG"
}

build_and_push ingest/video-segmenter vss-video-segmenter
build_and_push ingest/video-reasoner   vss-video-reasoner
build_and_push ingest/video-embedder   vss-video-embedder
build_and_push ingest/vastdb-writer    vss-video-vastdb
build_and_push enrichment/prompt-suggester vss-video-events

echo "Done. Pushed vastde functions (tag=$TAG) to $ECR"
