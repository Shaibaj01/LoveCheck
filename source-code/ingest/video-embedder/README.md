# Video Embedder

A VAST DataEngine serverless function that converts video reasoning text into vector embeddings for semantic search.

## What It Does

- Receives reasoning text from the `video-reasoner` function
- Embeds `dense_caption` into **text** vectors (`vectors`) via NVIDIA NIM
- Downloads the segment from S3 and embeds sampled frames into **visual** vectors (`vectors_visual`) when enabled
- Passes both embeddings and metadata to the next function in the pipeline
- Preserves all metadata (camera_id, capture_type, location, etc.)

## Easy to Adjust

Configure in `ingest/vss-video-ingest-secret-template.yaml`:

| Setting | Description |
|---------|-------------|
| **`embedding_local_nim`** | `true` = local NIM (no API key), `false` = NVIDIA Cloud (sends API key) |
| **`embeddinghost`** / **`embeddingport`** / **`embeddinghttpscheme`** | Endpoint to use (always required) |
| **`embeddingmodel`** | Embedding model name (e.g., `nvidia/llama-3.2-nv-embedqa-1b-v2`) |
| **`embeddingdimensions`** | Text vector dimensions (must match model output, e.g. 2048) |
| **`visual_embedding_enabled`** | When `true`, download segment from S3 and compute `vectors_visual` |
| **`visual_embedding_model`** | Multimodal embed model (e.g. `nvidia/llama-3.2-nemoretriever-1b-vlm-embed-v1`) |
| **`visual_embedding_dimensions`** | Visual vector dimensions (typically same as text, 2048) |
| **`nvidia_api_key`** | Required when `embedding_local_nim: false` (NVIDIA Cloud) |

For NVIDIA Cloud, set: `embeddinghost: integrate.api.nvidia.com`, `embeddingport: 443`, `embeddinghttpscheme: https`

## About the Function

- **Trigger**: Receives events from `video-reasoner` function
- **Input**: Reasoning text and metadata from video analysis
- **Output**: Vector embeddings and metadata
- **Processing**: Calls NVIDIA NIM embedding API to generate vectors
- **Validation**: Skips if reasoning content is empty or invalid

## What Runs It

- **Runtime**: VAST DataEngine serverless runtime
- **Image**: `your.registry/vss-video-embedder:v1` (placeholder — build with `vastde build` and push; see [Ingest pipeline guide](../../../deployments/dataengine-vss-ingest-pipeline/README.md#build-ingest-function-images))
- **Resources**: Configure CPU/Memory in DataEngine UI pipeline settings
- **Dependencies**: Python 3.11, NVIDIA NIM embedding API access

