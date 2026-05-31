# Video Reasoner

DataEngine function that analyzes video segments using **Cosmos-Reason2** to generate structured descriptions.

## What It Does

- Triggered when segments land in `video-chunks-segments` bucket
- Sends segment MP4 (base64) to Cosmos-Reason2
- Produces `dense_caption`, `vlm_structured`, and `reasoning_content`
- Perception lite (always on) → object list conditions main VLM
- Passes results to `video-embedder`

## Configuration

Configure in `deployments/dataengine-vss-ingest-pipeline/vss-gui-secret-file-template.yaml` (GUI) or `vss-cli-secret-file-template.yaml` (CLI):

### Cosmos-Reason2 Settings

| Setting | Default |
|---------|---------|
| `cosmos_host` | (required) |
| `cosmos_port` | 8001 |
| `cosmos_model` | ./Cosmos-Reason2-8B |
| `cosmos_max_tokens` | 4000 |
| `cosmos_temperature` | 0.2 |
| `perception_max_tokens` | 512 |

Local stack guide: `docs/COSMOS_LOCAL_STACK.md`

---

## Analysis Scenarios

Set `scenario` in ingest secret or per-video via S3 metadata:

| Scenario | Use Case |
|----------|----------|
| `surveillance` | Security cameras, safety monitoring |
| `traffic` | Traffic cameras, vehicle detection |
| `nhl` | Hockey game analysis |
| `sports` | General sports footage |
| `retail` | Store cameras, customer behavior |
| `warehouse` | Industrial safety, PPE compliance |
| `egocentric` | First-person perspective |
| `general` | Generic video description (default) |

### Per-Video Override

Set `scenario` in S3 object metadata when uploading:

```python
s3_client.put_object(
    Bucket=bucket, Key=key, Body=video_content,
    Metadata={"scenario": "traffic"}
)
```

---

## Custom Prompts

For full control, provide a custom prompt via S3 metadata (overrides scenario):

```python
Metadata={"custom-prompt": "Analyze safety violations..."}
```

Or use the GUI:
- **Manual Upload / Streaming / Batch Sync**: Check "Use custom prompt"

Max 800 characters. URL-encoded automatically.

### Adding New Scenarios

1. Edit `source-code/ingest/video-reasoner/common/prompts.py`
2. Add to `SCENARIO_PROMPTS` dictionary
3. Update ingest secret with new scenario name
4. Redeploy in DataEngine UI

---

## Runtime

- **Image**: `your.registry/vss-video-reasoner:v1` (placeholder — build with `vastde build` and push; see [Ingest pipeline guide](../../../deployments/dataengine-vss-ingest-pipeline/README.md#build-ingest-function-images))
- **Trigger**: S3 bucket event on `video-chunks-segments`
