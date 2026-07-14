# Running models on the neurondc `bc47cc` GB200 host

How each model is served on `cmp-gpu-000a.bc47cc.sea1.neurondc.com` (NVIDIA **GB200**,
`aarch64`) and exposed through the neurondc gateway.

> Reference: [bc47cc inference setup](https://mantledc.getoutline.com/s/90eda0b1-c7d8-448c-a487-0c2d03fee226)

---

## Environment

| Item | Value |
|------|-------|
| Node | `cmp-gpu-000a.bc47cc.sea1.neurondc.com` (internal `10.33.107.20`) |
| Arch | `aarch64` (Grace ARM CPU + Blackwell GPU) — **not x86** |
| Public base URL | `https://beta-api.neurondc.com` |
| Bearer token | `4d4c84fc1c00cbf2eec3e9cef56468c66e18454dbf3bfad215d0930706b408cd` |
| Model dirs | `/mnt/storage/dpeer` (shared on node + jumphost) |

SSH:

```sh
ssh cmp-gpu-000a.bc47cc.sea1.neurondc.com
```

### Slot → port rule (important)

The gateway pins each slot name to a **fixed** upstream port on `10.33.107.20`. The
container **must** publish that exact port, or the public route returns `502 Bad Gateway`.

| Slot | Host port | GPU | Model | Runtime |
|------|-----------|-----|-------|---------|
| `model-6b140a` | 8000 | – | opt-125m (placeholder) | vLLM |
| `model-6b140b` | 8001 | 0 | cosmos-reason2-8b | vLLM (aarch64) |
| `model-6b140c` | 8002 | 1 | cosmos-reason1-7b | vLLM (aarch64) |
| `model-6b140d` | 8003 | 3 | yolo-infer | custom Docker |
| `model-6b140e` | 8004 | 2 | cosmos-embed1 | custom Docker (native PyTorch, aarch64) |
| `model-6b140f` | 8005 | – | free | – |
| `model-6b140g` | 8006 | – | free | – |
| `model-6b140h` | 8007 | – | free | – |

Public route pattern: `https://beta-api.neurondc.com/bc47cc/<slot>/...`

Status / manage:

```sh
docker ps --all --filter label=inference-bootstrap.model_name
docker logs -f <slot>
docker rm -f <slot>
```

---

## One-time: NGC CLI (ARM64, no root)

```sh
mkdir -p ~/ngc-tools
curl -sLo ~/ngc-tools/ngccli.zip \
  https://api.ngc.nvidia.com/v2/resources/nvidia/ngc-apps/ngc_cli/versions/4.10.0/files/ngccli_arm64.zip
unzip -qo ~/ngc-tools/ngccli.zip -d ~/ngc-tools
chmod +x ~/ngc-tools/ngc-cli/ngc
~/ngc-tools/ngc-cli/ngc config set   # paste your nvidia-api-key when prompted
```

The vLLM image is downloaded automatically by `docker run` on first use.

---

## Cosmos-Reason2-8b — `model-6b140b` (GPU 0, port 8001)

Reasoning VLM. Served with the **aarch64** vLLM image over `/v1/chat/completions`.

```sh
# 1. Download weights
~/ngc-tools/ngc-cli/ngc registry model download-version \
  "nim/nvidia/cosmos-reason2-8b:1208-fp8-static-kv8" \
  --dest /mnt/storage/dpeer/cosmos-reason2-8b

# 2. Symlink the slot -> downloaded model dir
ln -sfn /mnt/storage/dpeer/cosmos-reason2-8b/cosmos-reason2-8b_v1208-fp8-static-kv8 \
  /mnt/storage/dpeer/model-6b140b

# 3. Run (GPU 0, host 8001)
docker rm -f model-6b140b 2>/dev/null || true
docker run -d --name model-6b140b \
  --gpus '"device=0"' \
  --label inference-bootstrap.model_name=model-6b140b \
  --restart unless-stopped \
  -v /mnt/storage/dpeer/model-6b140b:/model \
  -p 8001:8000 \
  vllm/vllm-openai:v0.23.0-aarch64-ubuntu2404 \
  --model /model \
  --served-model-name model-6b140b \
  --trust-remote-code \
  --max-model-len 32768
```

Verify (remote):

```sh
export TOKEN='4d4c84fc1c00cbf2eec3e9cef56468c66e18454dbf3bfad215d0930706b408cd'
curl https://beta-api.neurondc.com/bc47cc/model-6b140b/v1/chat/completions \
  -H "Authorization: Bearer ${TOKEN}" \
  -H 'Content-Type: application/json' \
  -d '{
    "model": "model-6b140b",
    "messages": [{"role": "user", "content": "Analyze step-by-step why the sky appears blue."}],
    "temperature": 0.2
  }'
```

---

## Cosmos-Reason1-7b — `model-6b140c` (GPU 1, port 8002)

Same pattern as Reason2, different weights / slot / GPU / port.

```sh
# 1. Download weights
~/ngc-tools/ngc-cli/ngc registry model download-version \
  "nim/nvidia/cosmos-reason1-7b:1.1-fp8-dynamic" \
  --dest /mnt/storage/dpeer/cosmos-reason1-7b

# 2. Symlink the slot -> downloaded model dir
ln -sfn /mnt/storage/dpeer/cosmos-reason1-7b/cosmos-reason1-7b_v1.1-fp8-dynamic \
  /mnt/storage/dpeer/model-6b140c

# 3. Run (GPU 1, host 8002)
docker rm -f model-6b140c 2>/dev/null || true
docker run -d --name model-6b140c \
  --gpus '"device=1"' \
  --label inference-bootstrap.model_name=model-6b140c \
  --restart unless-stopped \
  -v /mnt/storage/dpeer/model-6b140c:/model \
  -p 8002:8000 \
  vllm/vllm-openai:v0.23.0-aarch64-ubuntu2404 \
  --model /model \
  --served-model-name model-6b140c \
  --trust-remote-code \
  --max-model-len 32768
```

Verify: same curl as Reason2, swapping `model-6b140b` → `model-6b140c`.

---

## YOLO11 infer — `model-6b140d` (GPU 3, port 8003)

Custom object-detection sidecar. Built from the local
[`yolo-infer/Dockerfile`](./yolo-infer/); code + weights are bind-mounted. Full
instructions: [`yolo-infer/README.md`](./yolo-infer/README.md).

```sh
# 1. Symlink the slot -> code dir
ln -sfn /mnt/storage/dpeer/yolo-infer /mnt/storage/dpeer/model-6b140d

# 2. Build the image
cd /mnt/storage/dpeer/yolo-infer
docker build -t yolo-infer:cu130 .

# 3. Run (GPU 3, host 8003 -> container 8000)
docker rm -f model-6b140d 2>/dev/null || true
docker run -d --name model-6b140d \
  --gpus '"device=3"' \
  --label inference-bootstrap.model_name=model-6b140d \
  --restart unless-stopped \
  -v /mnt/storage/dpeer/model-6b140d:/app -w /app \
  -p 8003:8000 \
  -e YOLO_MODEL=yolo11s.pt \
  -e YOLO_DEVICE=0 \
  -e YOLO_CONF=0.4 \
  -e YOLO_CONFIG_DIR=/tmp/Ultralytics \
  yolo-infer:cu130
```

Verify:

```sh
curl -s localhost:8003/healthz
# remote: https://beta-api.neurondc.com/bc47cc/model-6b140d/v1/infer
```

> **502 on `/v1/infer` while `/healthz` is fine?** The container lost its live GPU
> attach — `healthz` shows `cuda_available:false` and the first real inference
> fails with `Invalid CUDA 'device=0' ... torch.cuda.is_available(): False`, which
> the gateway surfaces as `502`. This happens after a docker daemon / nvidia-runtime
> reload even though `docker inspect` still lists the GPU in `DeviceRequests`.
> **Fix:** recreate the container (`docker rm -f model-6b140d` + the `docker run`
> above) to re-trigger GPU injection; `healthz` should then report
> `cuda_available:true`.

---

## Cosmos-Embed1 — `model-6b140e` (GPU 2, port 8004) — native PyTorch

Joint video-text embedding model (256-dim text + video vectors). NVIDIA ships it
**only as a NIM container** (`nvcr.io/nim/nvidia/cosmos-embed1:1.1.0`), which is
**amd64-only** (`Multi-Arch Support: False`) and crash-loops on the GB200 (arm64)
with `exec /bin/bash: exec format error`.

**Solution:** skip the NIM and serve the raw HuggingFace weights with a small
FastAPI/PyTorch app on the **aarch64 CUDA PyTorch base image** — same "load raw
weights on ARM" trick as the Reason1/2 vLLM slots. The server exposes the exact
`POST /v1/embeddings` contract the NIM did, so no app-side changes beyond pointing
the secret at it. Code + full deploy steps: [`cosmos-embed1-pytorch/`](./cosmos-embed1-pytorch/)
(`README.md`, `DEPLOY.md`).

Why the NIM itself can't run here:
- **No arm64 image** — every tag (`1.1.0`, `1.1`, `1.0.0`, `1`, `latest`) is amd64.
- **No vLLM path** — vLLM has no implementation for the Cosmos-Embed1 video-text
  encoder architecture, so the aarch64 vLLM image can't serve it.
- **Not on NVIDIA Cloud** — `integrate.api.nvidia.com` serves text embedders
  (e.g. `nvidia/nv-embedqa-e5-v5`), not `nvidia/cosmos-embed1`.

```sh
# 1. Copy code to the node
scp -r deployments/vss-gpu-services/cosmos-embed1-pytorch \
  cmp-gpu-000a.bc47cc.sea1.neurondc.com:/mnt/storage/dpeer/cosmos-embed1-pytorch

# 2. Build (aarch64 base ships torch/torchvision for ARM CUDA)
cd /mnt/storage/dpeer/cosmos-embed1-pytorch
docker build -t cosmos-embed1-pytorch:224p .

# 3. Run (GPU 2, host 8004 -> container 8000). Weights download to the mounted HF cache on first start.
docker rm -f model-6b140e 2>/dev/null || true
docker run -d --name model-6b140e \
  --gpus '"device=2"' \
  --label inference-bootstrap.model_name=model-6b140e \
  --restart unless-stopped \
  -e COSMOS_MODEL_ID=nvidia/Cosmos-Embed1-224p \
  -e COSMOS_NUM_FRAMES=8 -e COSMOS_EMBED_DIM=256 \
  -v /mnt/storage/dpeer/hf-cache:/models/hf \
  -p 8004:8000 \
  cosmos-embed1-pytorch:224p
```

Verify:

```sh
# local
curl -s localhost:8004/health
# {"status":"ok","model":"nvidia/Cosmos-Embed1-224p","dim":256,"frames":8}

# remote (gateway — Bearer token required, else 401)
export TOKEN='4d4c84fc1c00cbf2eec3e9cef56468c66e18454dbf3bfad215d0930706b408cd'
curl -s https://beta-api.neurondc.com/bc47cc/model-6b140e/health \
  -H "Authorization: Bearer ${TOKEN}"
```

> **Gotchas (already fixed in the code/Dockerfile/requirements):**
> - The image must `COPY server.py router.py embedder.py` (not just `server.py`).
> - `transformers` must be pinned `==4.44.2` — 4.45+ removed
>   `find_pruneable_heads_and_indices`, which Cosmos-Embed1's QFormer imports.
> - Video frames must be fed **channel-first `BTCHW`**. Frames decode channel-last
>   `(T, H, W, 3)`, so `embed_videos` permutes to `(B, n, 3, H, W)` before the
>   processor. Without it the model reads the height (e.g. `1080`) as the channel
>   and returns `500: Expected tensor of shape BTCHW ... got channel size 1080`,
>   which surfaces at the ingest embedder as a failed **visual** embedding
>   (text still succeeds, so it's easy to miss).

> **Re-ingest required:** this server's frame sampling differs from the NIM, so its
> vectors live in a different space. Use a fresh bucket/schema/collection and
> re-embed all content; don't mix NIM and PyTorch vectors.
