# Cosmos-Embed1 — PyTorch server (arm64 / GB200)

Native-PyTorch replacement for the amd64-only Cosmos-Embed1 NIM, so it runs on a
GB200 (`aarch64`). Exposes the same `POST /v1/embeddings` contract the VSS
ingest + retrieval clients already use — the only app change is pointing the secret's
`embeddinghost`/`embeddingport` at this service.

See `DEPLOY.md` for full step-by-step deployment. The commands below use these
placeholders: `$HOST` (node), `$SLOT` (container/slot name), `$PORT` (host port),
`$GPU` (free GPU index), `$DEPLOY_DIR` (code path on the node), `$HF_CACHE` (weights cache).

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
ssh $HOST
cd $DEPLOY_DIR                 # copy this dir here first
docker build -t cosmos-embed1-pytorch:224p .
```

## Run (GPU $GPU, host $PORT -> container 8000)
```sh
docker rm -f $SLOT 2>/dev/null || true
docker run -d --name $SLOT \
  --gpus "\"device=$GPU\"" \
  --label inference-bootstrap.model_name=$SLOT \
  --restart unless-stopped \
  -v $HF_CACHE:/models/hf \
  -p $PORT:8000 \
  cosmos-embed1-pytorch:224p
```
> First start downloads the weights into the mounted HF cache.

## Verify
```sh
# health
curl -s localhost:$PORT/health

# text
curl -s localhost:$PORT/v1/embeddings -H 'Content-Type: application/json' -d '{
  "input": "a red car driving at night", "request_type": "query", "model": "nvidia/cosmos-embed1"
}' | python3 -c "import sys,json;d=json.load(sys.stdin);print('dim',len(d['data'][0]['embedding']))"

# video (base64 an mp4 first)
B64=$(base64 -w0 clip.mp4)
curl -s localhost:$PORT/v1/embeddings -H 'Content-Type: application/json' -d "{
  \"input\": \"data:video/mp4;base64,${B64}\", \"request_type\": \"query\", \"model\": \"nvidia/cosmos-embed1\"
}" | python3 -c "import sys,json;d=json.load(sys.stdin);print('dim',len(d['data'][0]['embedding']))"

# remote route (if the node is fronted by a gateway — Bearer token usually REQUIRED, else 401)
export TOKEN=<gateway-bearer-token>
curl -s https://<gateway-host>/<tenant>/<slot>/health \
  -H "Authorization: Bearer ${TOKEN}"

curl -s https://<gateway-host>/<tenant>/<slot>/v1/embeddings \
  -H "Authorization: Bearer ${TOKEN}" -H 'Content-Type: application/json' \
  -d '{"input":"a red car driving at night","request_type":"query"}' \
  | python3 -c "import sys,json;print('dim',len(json.load(sys.stdin)['data'][0]['embedding']))"
```

## Point VSS at it
In `backend-secret.yaml` (retrieval) and the ingest function secret:
```yaml
embedding_local_nim: true
embeddinghost: <node-ip-or-gateway-host>
embeddingport: <port>
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
- Pick a free GPU index for the slot.
