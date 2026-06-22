#!/usr/bin/env bash
# Symlink shared/ingest_metadata.py for local Python runs (optional — Docker COPY handles images).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SHARED="$ROOT/shared/ingest_metadata.py"

if [[ ! -f "$SHARED" ]]; then
  echo "Missing canonical file: $SHARED" >&2
  exit 1
fi

link_one() {
  local dest="$1"
  mkdir -p "$(dirname "$dest")"
  ln -sf "$SHARED" "$dest"
}

link_one "$ROOT/retrieval/video-backend/src/ingest_metadata.py"
link_one "$ROOT/video-streaming/src/ingest_metadata.py"
link_one "$ROOT/video-batch-sync/src/ingest_metadata.py"

echo "Linked ingest_metadata.py → shared/ingest_metadata.py (backend, streaming, batch-sync)."
