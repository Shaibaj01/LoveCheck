#!/usr/bin/env bash
# Build and push DataEngine (vastde) pipeline function images.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
if [[ -z "${REGISTRY:-}" ]]; then
  echo "error: set REGISTRY to your registry prefix (e.g. REGISTRY=your.registry/vss)" >&2
  echo "  example: REGISTRY=your.registry/vss TAG=v1 $0" >&2
  exit 1
fi
TAG="${TAG:-v1}"

build_and_push() {
  local dir="$1"
  local func_name="$2"
  local image_name="${3:-$func_name}"

  echo "==> $func_name ($dir)"
  cd "$ROOT/$dir"
  vastde functions build "$func_name"
  docker tag "$func_name" "$REGISTRY/$image_name:$TAG"
  docker push "$REGISTRY/$image_name:$TAG"
}

build_and_push ingest/video-segmenter vss-video-segmenter
build_and_push ingest/video-detector   vss-video-detector
build_and_push ingest/video-reasoner   vss-video-reasoner
build_and_push ingest/video-embedder   vss-video-embedder
build_and_push ingest/vastdb-writer    vss-video-vastdb
build_and_push enrichment/prompt-suggester vss-video-events

echo "Done. Pushed vastde functions (tag=$TAG) to $REGISTRY"
