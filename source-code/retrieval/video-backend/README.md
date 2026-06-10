# Video Backend

REST API service for video search, authentication, and management.

## Table of Contents

- [User Authentication](#user-authentication)
- [Local NIM vs NVIDIA Cloud](#local-nim-vs-nvidia-cloud)
- [GUI Settings](#gui-settings)
- [Custom AI Prompts](#custom-ai-prompts)
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

Users must have a VMS password set on their local account.

### How It Works

1. User enters username and password on the login page
2. Backend validates credentials against VMS `POST /api/token/{tenant}/` (falls back to `/api/token/`)
3. On success, backend issues a signed app JWT for the session

### Troubleshooting

- **Auth fails**: Verify user has a VMS password and `vast_host` / `tenant_name` match the cluster
- **Multi-tenant**: Set `tenant_name` to the correct tenant in `backend-secret.yaml`
- **Logs**: `kubectl logs -n <namespace> -l app=video-backend`

---

## Local NIM vs NVIDIA Cloud

| Setting | `true` (Local NIM) | `false` (NVIDIA Cloud) |
|---------|-------------------|------------------------|
| `embedding_local_nim` | No API key sent | Sends `nvidia_api_key` |
| `llm_local_nim` | No API key sent | Sends `nvidia_api_key` |

- **Local NIM**: Set flag to `true`, configure `host`/`port`/`scheme` for your endpoint
- **NVIDIA Cloud**: Set flag to `false`, use `integrate.api.nvidia.com:443`, set `nvidia_api_key`

---

## GUI Settings

### Advanced Search & AI Settings (Settings → Advanced Search & AI Settings)

| Setting | Description | Default |
|---------|-------------|---------|
| Max Clip Cards | Grouped upload cards returned (`top_k`) | 15 |
| LLM Clips Analyzed | Clip cards sent to LLM with timeline evidence | 3 |
| Caption vs Video Weight | Hybrid search blend (`hybrid_text_weight`) | 0.6 |
| Minimum Similarity | Hybrid score threshold for clip cards | 0.1 |

### System Prompt (Settings → System Prompt)

Customize the LLM prompt for synthesizing search results. Stored in browser localStorage.

### Time Filtering

Filter search results by upload time:
- Presets: Last 5 min, 15 min, 1 hour, 24 hours, 1 week
- Custom: Select specific date range

---

## Custom AI Prompts

When uploading videos, check **"Use custom prompt"** to provide a custom AI reasoning prompt instead of predefined scenarios.

- Max 800 characters
- Overrides scenario selection
- Available in: Manual Upload, Streaming, Batch Sync dialogs

---

## Agent APIs

| Endpoint | Description |
|----------|-------------|
| `GET /api/v1/tools/segments?original_video=s3://...` | List segments for a parent video |
| `GET /api/v1/tools/segment?source=s3://...` | Get one segment row |
| `POST /api/v1/tools/search` | Same body as `/api/v1/search` (hybrid/text/visual) |
| `POST /api/v1/agent/ask` | Ask a question (global search or video-specific with `original_video`) |

Search is **always hybrid** (caption + video vectors). ACL, time filters, tags, and metadata filters still apply on both VastDB branches.
