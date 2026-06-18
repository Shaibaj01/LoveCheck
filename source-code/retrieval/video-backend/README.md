# Video Backend

REST API for video search, explore browse, dashboard stats, suggestions, authentication, and agent tools.

## Table of Contents

- [User Authentication](#user-authentication)
- [Local NIM vs NVIDIA Cloud](#local-nim-vs-nvidia-cloud)
- [GUI Settings](#gui-settings)
- [Custom AI Prompts](#custom-ai-prompts)
- [Explore & Synthesize](#explore--synthesize)
- [Suggestions & Dashboard](#suggestions--dashboard)
- [Agent APIs](#agent-apis)

---

## User Authentication

Users authenticate with their **VAST username + password** (same as VMS login).

### Setup

Configure backend secret (`deployments/vss-k8s-application/backend-secret.yaml`):

```yaml
vast_host: "<vms-ip-or-hostname>"
tenant_name: "default"
jwt_secret: "<openssl rand -hex 32>"
```

### How It Works

1. User enters username and password on the login page
2. Backend validates against VMS `POST /api/token/{tenant}/`
3. On success, backend issues a signed app JWT for the session

---

## Local NIM vs NVIDIA Cloud

| Setting | `true` (Local NIM) | `false` (NVIDIA Cloud) |
|---------|-------------------|------------------------|
| `embedding_local_nim` | No API key sent | Sends `nvidia_api_key` |
| `llm_local_nim` | No API key sent | Sends `nvidia_api_key` |

---

## GUI Settings

### Advanced Search & AI Settings

| Setting | Description | Default |
|---------|-------------|---------|
| Max Clip Cards | Grouped upload cards (`top_k`) | 15 |
| LLM Clips Analyzed | Clip cards sent to LLM | 3 |
| Caption vs Video Weight | Hybrid blend (`hybrid_text_weight`) | 0.6 |
| Minimum Similarity | Score threshold | 0.1 |

### Time Filtering

Presets (5m, 15m, 1h, 24h, 7d) or custom date range on upload timestamp.

---

## Custom AI Prompts

Per-upload custom reasoning prompt (max 800 chars) in Upload, Streaming, and Batch Sync dialogs.

---

## Explore & Synthesize

| Endpoint | Description |
|----------|-------------|
| `GET /api/v1/videos/explore` | Browse parent videos by upload date (`scope`, `date`, `limit`, `offset`) |
| `POST /api/v1/videos/synthesize` | On-demand LLM summary over all segments for one `original_video` |

Explore returns chunk cards (same shape as search `chunk_results`) without vector scores. Response includes `table_available` / `table_message` when VastDB is empty or unreadable.

---

## Suggestions & Dashboard

| Endpoint | Description |
|----------|-------------|
| `GET /api/v1/suggestions` | Search prompts + key events from `vss2-prompts-events` (prompt-suggester) |
| `GET /api/v1/dashboard/stats` | VastDB overview, ingest quality, S3 inventory, recent videos (`scope`) |

Suggestions filters key events to videos the user can access. Returns `prompts_table_available` / `table_message` when the prompts table is missing.

---

## Agent APIs

Thin wrappers for external agents (AgentEngine, custom automation). All require the same JWT as the UI.

### Tools — `/api/v1/tools`

| Endpoint | Agent tool | Description |
|----------|------------|-------------|
| `GET /tools/segments?original_video=…` | `list_segments` | All segment rows for a parent video |
| `GET /tools/segment?source=…` | `get_segment_json` | One segment by clip URI |
| `POST /tools/search` | `search_hybrid` | Same body as `POST /search` |
| `GET /tools/explore` | `explore_timeline` | Same params as `GET /videos/explore` |
| `POST /tools/synthesize` | `synthesize_video` | Same body as `POST /videos/synthesize` |

### Agent — `/api/v1/agent`

| Endpoint | Description |
|----------|-------------|
| `POST /agent/ask` | `{ question, original_video?, top_k }` — video-specific segments + LLM, or global hybrid search |
| `POST /agent/search-and-answer` | Full `VideoSearchRequest` body → answer + chunk evidence |

**Agent response shape:**

```json
{
  "answer": "…",
  "tool_used": "search_hybrid | video_segments",
  "evidence": { }
}
```

Search is **always hybrid** (caption + video vectors). ACL, time filters, tags, and metadata filters apply.
