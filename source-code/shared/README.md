# Shared cross-service modules

## `ingest_metadata.py`

Single source of truth for ingest/upload metadata (field labels, capture types, scenario labels, S3 mapping, custom-prompt limit).

| Consumer | How it gets the module |
|----------|-------------------------|
| **video-backend** | Docker: `COPY shared/ingest_metadata.py` into image. Local: optional symlink via `link-ingest-metadata.sh` |
| **video-streaming** | Same |
| **video-batch-sync** | Same |
| **video-frontend** | Runtime: `GET /api/v1/metadata/ingest-config` |

Scenario **prompt text** stays in `ingest/video-reasoner/common/prompts.py`.

There are **no committed copies** under service `src/` directories.

---

## Editing metadata

1. Change **`source-code/shared/ingest_metadata.py`**
2. For a new analysis scenario, also add prompt text to `prompts.py`
3. Rebuild affected Docker images (see below)

---

## Docker builds

Build from **`source-code/`** as context (canonical `shared/` is copied into each image), or use the helper script:

```bash
source-code/scripts/build-retrieval-images.sh   # backend, frontend, streaming, batch-sync
```

Manual builds:

```bash
cd source-code

docker buildx build -f retrieval/video-backend/Dockerfile -t your.registry/vss-video-backend:v2 --push .

docker buildx build -f retrieval/video-frontend/Dockerfile -t your.registry/vss-video-frontend:v2 --push retrieval/video-frontend

docker buildx build -f video-streaming/Dockerfile -t your.registry/vss-video-streaming:v2 --push .

docker buildx build -f video-batch-sync/Dockerfile -t your.registry/vss-video-batch-sync:v2 --push .
```

Frontend still uses `retrieval/video-frontend/` as context (no shared Python module).

See [scripts README](../scripts/README.md) for `ECR` / `TAG` overrides.

---

## Local Python dev (without Docker)

One-time symlink (optional):

```bash
source-code/scripts/link-ingest-metadata.sh
```

This creates `src/ingest_metadata.py` → `shared/ingest_metadata.py` in backend, streaming, and batch-sync. Symlinks are gitignored.

---
