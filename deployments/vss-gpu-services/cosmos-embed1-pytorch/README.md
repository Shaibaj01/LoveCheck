# Cosmos-Embed1 — PyTorch server (arm64 / GB200)

Native-PyTorch replacement for the amd64-only Cosmos-Embed1 NIM, so it runs on the
`bc47cc` GB200 (`aarch64`). Exposes the same `POST /v1/embeddings` contract the VSS
ingest + retrieval clients already use — the only app change is pointing the secret's
`embeddinghost`/`embeddingport` at this service.

Slot: **`model-6b140e`**, host port **8004** (per `../neurondc-gb200-models.md`).

## Why PyTorch (not the NIM)
The NIM is a prebuilt **amd64** container (TensorRT engines compiled for x86_64) and
crash-loops on the Grace ARM CPU with `exec format error`. PyTorch loads the raw model
weights and dispatches to **arm64-native** CUDA kernels at runtime, so the same weights
run on the GB200 (same trick as the vLLM Reason1/2 slots).

## What the server owns (that the NIM hid)
`client → data:video/mp4;base64 → server → decode → 8 frames → get_video_embeddings`

- MP4 decode + **8-frame uniform sampling** (`sample_frames()`), the single source of
  truth for both ingest and query so vectors can't drift into different spaces.
- Image query → tiled to 8 frames (Cosmos-Embed1 has no image-only path).
- Text → `get_text_embeddings` (Bert tokenizer, max_len 128).
- Output L2-normalized, 256-dim.

## Build (on the GB200 node, aarch64)
```sh
ssh cmp-gpu-000a.bc47cc.sea1.neurondc.com
cd /mnt/storage/dpeer/cosmos-embed1-pytorch    # copy this dir here
docker build -t cosmos-embed1-pytorch:224p .
```

## Run (slot model-6b140e, GPU 2, host 8004 -> container 8000)
```sh
docker rm -f model-6b140e 2>/dev/null || true
docker run -d --name model-6b140e \
  --gpus '"device=2"' \
  --label inference-bootstrap.model_name=model-6b140e \
  --restart unless-stopped \
  -v /mnt/storage/dpeer/hf-cache:/models/hf \
  -p 8004:8000 \
  cosmos-embed1-pytorch:224p
```
> First start downloads the weights into the mounted HF cache.

## Verify
```sh
# health
curl -s localhost:8004/health

# text
curl -s localhost:8004/v1/embeddings -H 'Content-Type: application/json' -d '{
  "input": "a red car driving at night", "request_type": "query", "model": "nvidia/cosmos-embed1"
}' | python3 -c "import sys,json;d=json.load(sys.stdin);print('dim',len(d['data'][0]['embedding']))"

# video (base64 an mp4 first)
B64=$(base64 -w0 clip.mp4)
curl -s localhost:8004/v1/embeddings -H 'Content-Type: application/json' -d "{
  \"input\": \"data:video/mp4;base64,${B64}\", \"request_type\": \"query\", \"model\": \"nvidia/cosmos-embed1\"
}" | python3 -c "import sys,json;d=json.load(sys.stdin);print('dim',len(d['data'][0]['embedding']))"

# remote route
# https://beta-api.neurondc.com/bc47cc/model-6b140e/v1/embeddings
```

## Point VSS at it
In `backend-secret.yaml` (retrieval) and the ingest function secret:
```yaml
embedding_local_nim: true
embeddinghost: 10.33.107.20     # or the gateway host
embeddingport: 8004
embeddingmodel: nvidia/cosmos-embed1
embeddingdimensions: 256
```

## IMPORTANT — re-ingest from scratch
Existing `vectors` / `vectors_visual` were made by the **NIM**. This server's
preprocessing (frame sampling) differs, so its vectors live in a **different space**.
Use a fresh bucket/schema/collection and **re-embed all content** with this server, then
query with it too. Do not mix NIM and PyTorch vectors in one collection.

## Config (env)
| Var | Default | Notes |
|-----|---------|-------|
| `COSMOS_MODEL_ID` | `nvidia/Cosmos-Embed1-224p` | `-448p` for higher fidelity (heavier) |
| `COSMOS_NUM_FRAMES` | `8` | model was trained on 8; changing risks quality |
| `COSMOS_EMBED_DIM` | `256` | must match the VastDB vector column |

## TODO / verify before trusting
- Confirm `get_video_embeddings` / `get_text_embeddings` output attribute name on the
  pinned model revision (`server.py:_extract` handles common variants).
- Confirm `AutoProcessor(videos=...)` expects `(B, T, H, W, 3)` uint8 for this revision.
- Pick GPU index for the slot (README uses device 2; adjust to a free GPU).
