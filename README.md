# VAST DataEngine - Video Search and Summarization (VSS) Foundation Stack


- A Real-Time Video Search and Analysis system powered by [VAST DataEngine](https://www.vastdata.com/platform/dataengine), using [Nvidia NIM's](https://www.nvidia.com/en-eu/ai-data-science/products/nim-microservices/) & [Cosmos-Reason Models](https://huggingface.co/nvidia/Cosmos-Reason2-8B).

- This Blueprint is were released to bridge the gap between [NVIDIA’s VSS reference architectures](https://build.nvidia.com/nvidia/video-search-and-summarization/blueprintcard), and showcases the e2e utilization of the full VAST AI OS production-grade capabilities,
including Agentic & Serverless Event-based Compute Framework and VastDB Vector-Store.

---

## Overview

The system has two main parts:
1. **K8s Application** - Web UI and REST API (Kubernetes)
2. **Ingest Pipeline** - Serverless video processing (VAST DataEngine)

![VSS Blueprint Architecture](source-code/video-demo-diagram.png) — see also the interactive diagram in the app (**Show Blueprint Diagram**) or [`blueprint.html`](source-code/retrieval/video-frontend/src/assets/blueprint.html)

---

## Deployment

| Component | Guide |
|-----------|-------|
| **VSS - Retrieval Web UI; K8s Application** (Backend, Frontend, Streaming, Batch Sync) | [vss-k8s-application](deployments/vss-k8s-application/README.md) |
| **VSS - DataEngine; Ingest Pipeline** (Segmenter, Reasoner, Embedder, Writer) | [dataengine-vss-ingest-pipeline](deployments/dataengine-vss-ingest-pipeline/README.md) |

### Quick Start

1. **Deploy K8s Application:**
   ```bash
   cd deployments/vss-k8s-application
   vim backend-secret.yaml  # Configure credentials
   ./QUICK_DEPLOY.sh <namespace> <cluster_name>
   ```

2. **Deploy Ingest Pipeline** (choose one):
   - **Using GUI:** Configure `vss-gui-secret-file-template.yaml`, then use DataEngine UI
   - **Using CLI:** Configure `vss-cli-secret-file-template.yaml`, then run vastde commands
   
   See [Ingest Pipeline Guide](deployments/dataengine-vss-ingest-pipeline/README.md) for full instructions.

3. **Test:** Upload a video and search at `http://video-lab.<cluster_name>.vastdata.com`

---

## Key Features

| Feature | Description | Documentation |
|---------|-------------|---------------|
| **Video Analysis Prompts** | Configurable AI scenarios (surveillance, traffic, live_driving, etc.) | [video-reasoner](source-code/ingest/video-reasoner/README.md) |
| **Ingest metadata config** | Single definition for upload metadata UI + S3 mapping (`ingest_metadata.py`) | [shared](source-code/shared/README.md) |
| **Custom AI Prompts** | Per-video custom prompts (max length in `ingest_metadata.py`) | [video-reasoner](source-code/ingest/video-reasoner/README.md#custom-prompts) |
| **Metadata Filters** | Filter by camera_id, location, capture_type | [ingest](source-code/ingest/README.md) |
| **Advanced Search & AI Settings** | Max clip cards, synthesis clip count, caption/video weight, similarity | [video-backend](source-code/retrieval/video-backend/README.md#gui-settings) |
| **Explore mode** | Browse indexed uploads by day and location — no query; summarize any video on demand | [video-frontend](source-code/retrieval/video-frontend/README.md#application-modes) |
| **Data Dashboard** | VastDB stats, ingest health, S3 pipeline inventory, live key events | [video-frontend](source-code/retrieval/video-frontend/README.md#application-modes) |
| **Search suggestions & key events** | Cosmos-generated prompts from prompt-suggester → VastDB `vss-prompts-events` | [prompt-suggester](source-code/enrichment/prompt-suggester/README.md) |
| **Agent APIs** | Tool wrappers + grounded Q&A for external agents | [video-backend](source-code/retrieval/video-backend/README.md#agent-apis) |
| **Time Filtering** | Filter by upload time (presets or custom range) | [video-backend](source-code/retrieval/video-backend/README.md#gui-settings) |
| **Video Streaming** | Capture YouTube videos to S3 | [video-streaming](source-code/video-streaming/README.md) |
| **Batch Sync** | Copy MP4 files between S3 buckets | [video-batch-sync](source-code/video-batch-sync/README.md) |
| **Authentication** | VAST username + S3 secret key | [video-backend](source-code/retrieval/video-backend/README.md) |

---

## Component Documentation

| Component | Description |
|-----------|-------------|
| [shared](source-code/shared/README.md) | Cross-service modules (`ingest_metadata.py` — upload metadata UI + S3) |
| [scripts](source-code/scripts/README.md) | Build scripts for retrieval images and DataEngine functions |
| [video-backend](source-code/retrieval/video-backend/README.md) | REST API, authentication, search |
| [video-frontend](source-code/retrieval/video-frontend/README.md) | Angular web UI (Search, Explore, Dashboard) |
| [prompt-suggester](source-code/enrichment/prompt-suggester/README.md) | Scheduled search prompts + key events → VastDB |
| [video-streaming](source-code/video-streaming/README.md) | YouTube capture service |
| [video-batch-sync](source-code/video-batch-sync/README.md) | S3 batch copy service |
| [video-segmenter](source-code/ingest/video-segmenter/README.md) | Splits videos into segments |
| [video-detector](source-code/ingest/video-detector/README.md) | YOLO11 object detection + bbox sidecars |
| [video-reasoner](source-code/ingest/video-reasoner/README.md) | AI video analysis |
| [video-embedder](source-code/ingest/video-embedder/README.md) | Vector embeddings |
| [vastdb-writer](source-code/ingest/vastdb-writer/README.md) | Stores vectors in VastDB |

---

## Pipeline Flow

```
Upload Video → vss-chunks bucket
                    ↓
            video-segmenter (5s segments)
                    ↓
            video-detector (YOLO11 → object_classes + bbox sidecars)
                    ↓
            video-reasoner (Cosmos-Reason2 → reasoning_content)
                    ↓
            video-embedder (vectors text + vectors_visual video)
                    ↓
            vastdb-writer (segment rows in VastDB)
                    ↓
              Search Ready
                    ↓
         prompt-suggester (optional enrichment)
                    ↓
         vss-prompts-events (search prompts + key events)
```

**Search flow:** query embed (Cosmos-Embed1) → hybrid search → clip cards with upload-time badge and match timeline → Cosmos-Reason2 synthesis → player with bbox overlay

**Explore flow:** browse by upload date and **location** (fully indexed chunks only) → clip cards with segment timeline and upload-time badge → full-chunk player with bbox toggle and **Summarize Video**

**Dashboard flow:** VastDB KPIs + ingest quality + S3 vs index alignment → key events table (from prompt-suggester) with in-place segment preview

**Agent flow:** `GET/POST /api/v1/tools/*` for VastDB/search/explore/synthesize → `POST /api/v1/agent/ask` or `/search-and-answer` for grounded answers

Interactive diagram: open **Show Blueprint Diagram** in the app, or `source-code/retrieval/video-frontend/src/assets/blueprint.html`

---

## Need Help?

- **K8s Deployment**: See [K8s Application Guide](deployments/vss-k8s-application/README.md#troubleshooting)
- **Ingest Pipeline**: See [Ingest Pipeline Guide](deployments/dataengine-vss-ingest-pipeline/README.md)
- **Community**: [VAST Community Forums](https://community.vastdata.com/)
