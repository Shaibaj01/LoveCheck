# Deploying Cosmos-Embed1 (PyTorch) on the GB200

Step-by-step to get this service running as slot **`model-6b140e`** on port **8004** on
`cmp-gpu-000a.bc47cc.sea1.neurondc.com` (aarch64). See `../neurondc-gb200-models.md` for
the host/slot conventions.

---

## 0. Prerequisites (once)
- SSH access to the node.
- A free GPU index (Reason1/2 use GPU 0/1, YOLO uses GPU 3 — pick another, e.g. **2**).
- An NVIDIA NGC / HuggingFace token that can pull `nvidia/Cosmos-Embed1-224p`.

```sh
# confirm free GPUs
ssh cmp-gpu-000a.bc47cc.sea1.neurondc.com nvidia-smi
# confirm the slot port is free
ssh cmp-gpu-000a.bc47cc.sea1.neurondc.com 'docker ps --filter publish=8004'
```

---

## 1. Copy the code to the node
From your laptop, in the repo root:

```sh
scp -r deployments/vss-gpu-services/cosmos-embed1-pytorch \
  cmp-gpu-000a.bc47cc.sea1.neurondc.com:/mnt/storage/dpeer/cosmos-embed1-pytorch
```

(Or `git clone`/`git pull` the branch on the node if it has repo access.)

---

## 2. Build the image (on the node, aarch64)
```sh
ssh cmp-gpu-000a.bc47cc.sea1.neurondc.com
cd /mnt/storage/dpeer/cosmos-embed1-pytorch
docker build -t cosmos-embed1-pytorch:224p .
```

> The base `nvcr.io/nvidia/pytorch:25.01-py3` provides torch/torchvision built for
> aarch64 CUDA — this is the whole reason it runs where the amd64 NIM can't.

---

## 3. Provide the HF token & cache dir
The first run downloads the weights. Give it a token and a persistent cache so restarts
don't re-download.

```sh
mkdir -p /mnt/storage/dpeer/hf-cache
export HF_TOKEN=<your-hf-or-ngc-token>
```

---

## 4. Run as slot `model-6b140e` (GPU 2, host 8004 -> container 8000)
```sh
docker rm -f model-6b140e 2>/dev/null || true
docker run -d --name model-6b140e \
  --gpus '"device=2"' \
  --label inference-bootstrap.model_name=model-6b140e \
  --restart unless-stopped \
  -e HF_TOKEN=$HF_TOKEN \
  -e HUGGING_FACE_HUB_TOKEN=$HF_TOKEN \
  -e COSMOS_MODEL_ID=nvidia/Cosmos-Embed1-224p \
  -e COSMOS_NUM_FRAMES=8 \
  -e COSMOS_EMBED_DIM=256 \
  -v /mnt/storage/dpeer/hf-cache:/models/hf \
  -p 8004:8000 \
  cosmos-embed1-pytorch:224p
```

Watch it come up (weights download on first start):
```sh
docker logs -f model-6b140e     # wait for "Model ready in ..." and uvicorn "Application startup complete"
```

---

## 5. Verify

**Local (on the node):**
```sh
curl -s localhost:8004/health
# {"status":"ok","model":"nvidia/Cosmos-Embed1-224p","dim":256,"frames":8}

# text
curl -s localhost:8004/v1/embeddings -H 'Content-Type: application/json' -d '{
  "input": "a red car at night", "request_type": "query", "model": "nvidia/cosmos-embed1"
}' | python3 -c "import sys,json;print('dim',len(json.load(sys.stdin)['data'][0]['embedding']))"

# video
B64=$(base64 -w0 /path/to/clip.mp4)
curl -s localhost:8004/v1/embeddings -H 'Content-Type: application/json' -d "{
  \"input\": \"data:video/mp4;base64,${B64}\", \"request_type\": \"query\"
}" | python3 -c "import sys,json;print('dim',len(json.load(sys.stdin)['data'][0]['embedding']))"
```

**Remote (through the gateway):**
```sh
export TOKEN='4d4c84fc1c00cbf2eec3e9cef56468c66e18454dbf3bfad215d0930706b408cd'
curl -s https://beta-api.neurondc.com/bc47cc/model-6b140e/v1/embeddings \
  -H "Authorization: Bearer ${TOKEN}" -H 'Content-Type: application/json' \
  -d '{"input":"a red car at night","request_type":"query"}'
```
If the remote route returns `502`, the container isn't publishing **8004** — recheck `-p 8004:8000`.

---

## 6. Point VSS at this service
Update the retrieval `backend-secret.yaml` and the ingest function secret:

```yaml
embedding_local_nim: true
embeddinghost: 10.33.107.20      # node internal IP (or the gateway host)
embeddingport: 8004
embeddingmodel: nvidia/cosmos-embed1
embeddinghttpscheme: http
embeddingdimensions: 256
```

Re-apply the retrieval secret + restart backend:
```sh
# from deployments/vss-k8s-application on your machine
sed "s/NAMESPACE/vss2/g" backend-secret.yaml | kubectl apply -f -
kubectl rollout restart deployment/video-backend -n vss2
```

---

## 7. Re-ingest from scratch (REQUIRED)
Existing `vectors` / `vectors_visual` were made by the **NIM**; this server's frame
sampling differs, so its vectors are a **different space**. Do NOT mix them.

1. Create a fresh bucket/schema/collection (or wipe the current one).
2. Re-run ingest over all videos so segments + captions are re-embedded by this server.
3. Queries automatically use the same server → consistent space → correct search.

---

## Manage / troubleshoot
```sh
docker ps --all --filter label=inference-bootstrap.model_name
docker logs -f model-6b140e
docker rm -f model-6b140e          # stop/remove
docker stats model-6b140e          # GPU/mem use

# common issues
# - CUDA OOM        -> pick a less-loaded GPU or use 224p (not 448p)
# - 502 remote      -> container not on port 8004
# - download hangs  -> HF_TOKEN missing/invalid
# - exec format err -> you somehow pulled an amd64 image; this one must be built on the node
```

## Rollback
The old NIM slot (`model-6b140e`, port 8004) was blocked anyway. To revert VSS, point
the secret back at the previous x86 NIM host (`10.27.102.21:8002`) and re-ingest there.
