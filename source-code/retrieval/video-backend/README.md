# Video Backend

REST API service for video search, authentication, and management.

## Table of Contents

- [User Authentication](#user-authentication)
- [Local NIM vs NVIDIA Cloud](#local-nim-vs-nvidia-cloud)
- [GUI Settings](#gui-settings)
- [Custom AI Prompts](#custom-ai-prompts)
- [Agent & rollup APIs](#agent--rollup-apis)

---

## User Authentication

Users authenticate with their **VAST username + S3 secret key** (not DataEngine password).

### Setup

1. **Create Read-Only Role** (VMS > Administrators > Administrative Roles)
   - Name: `read-only`, Permissions: Read-only

2. **Create Manager User** (VMS > Administrators > Managers)
   - Name: `vssadmin`, attach to `read-only` role, uncheck "Password is temporary"

3. **Configure Backend Secret, including VMS ip & tenant name** (`deployments/vss-k8s-application/backend-secret.yaml`):
   ```yaml
   vast_admin_username: "vssadmin"
   vast_admin_password: "password"
   vast_host: ""
   tenant_name: "default"
   ```

### How It Works

1. User enters username, S3 secret key, VMS host, and tenant name
2. Backend validates credentials against VAST cluster
3. JWT token issued for session

### Troubleshooting

- **Auth fails**: Check `s3_endpoint` matches tenant's S3 endpoint
- **Multi-tenant**: Deploy separate backends per tenant with matching `s3_endpoint`
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

### Advanced LLM Settings (Settings → Advanced LLM Settings)

| Setting | Description | Default |
|---------|-------------|---------|
| LLM Analysis Count | Results sent to LLM | 3 |
| Max Search Results | Max segments returned | 15 |
| Minimum Similarity | Vector similarity threshold | 0.1 |

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

## Agent & rollup APIs

| Endpoint | Description |
|----------|-------------|
| `POST /api/v1/videos/summarize?original_video=s3://...` | Merge segment JSON into `row_kind=video_summary` |
| `GET /api/v1/videos/summary?original_video=s3://...` | Fetch existing video summary row |
| `GET /api/v1/tools/segments?original_video=s3://...` | List segments for a parent video |
| `GET /api/v1/tools/segment?source=s3://...` | Get one segment row |
| `POST /api/v1/tools/search` | Same body as `/api/v1/search` (hybrid/text/visual) |
| `POST /api/v1/agent/ask` | Ask a question (global search or video-specific with `original_video`) |

Search is **always hybrid** (caption + video vectors). ACL, time filters, tags, and metadata filters still apply on both VastDB branches. Segments only by default (`row_kind=segment`).
