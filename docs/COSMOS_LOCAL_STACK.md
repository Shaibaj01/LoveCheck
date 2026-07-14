# Local Cosmos stack (Reason2 + Embed1)

This blueprint can run against two local services (your docker commands).

## Services

| Service | Container / image | Host port | Used for |
|---------|-------------------|-----------|----------|
| **Cosmos-Reason2** | `vllm/vllm-openai` + `/model` | **8001** | `video-reasoner` (VLM + perception lite) |
| **Cosmos-Embed1** | `nvcr.io/nim/nvidia/cosmos-embed1:1.1.0` | **8002** (maps NIM :8000) | `video-embedder` + search backend |

## Secret alignment (`vss-gui-secret-file-template.yaml`)

- `cosmos_host` / `cosmos_port: 8001` / `cosmos_model: "./Cosmos-Reason2-8B"`
- `embeddinghost` / `embeddingport: 8002` / `embeddingmodel: nvidia/cosmos-embed1`
- `embeddingdimensions: 256` (required — Embed1 is **256-dim**, not 2048)

Backend `backend-secret.yaml` must use the same embed host/port/model/dimensions for search.

## How embeddings work in code

| Column | Ingest | API |
|--------|--------|-----|
| `vectors` | `reasoning_content` → Cosmos-Embed1 text (`request_type: query` / `bulk_text`) | Text query embed |
| `vectors_visual` | Segment **MP4** → Cosmos-Embed1 video (`data:video/mp4;base64,...`) | Text query embed (same model space) |

Client: `source-code/ingest/video-embedder/common/cosmos_embed_client.py`

## DataEngine networking

Use the IP/hostname that **DataEngine workers** can reach (not always `127.0.0.1` if functions run on another node). Same for the K8s backend calling embed for search.

## VastDB

Recreate the collection when switching to 256-dim vectors (was 2048 for Llama embed models).
