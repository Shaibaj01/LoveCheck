# Deploying Cosmos-Embed1 (PyTorch) on a GB200

Step-by-step to run this service as an inference slot on an **aarch64 GB200** node.
It serves the same `POST /v1/embeddings` contract as the NVIDIA NIM, but built for ARM
so it runs where the amd64-only NIM can't.

Set these once and reuse them in every command below:

```sh
HOST=<gb200-host>          # node hostname or IP you SSH into
SLOT=<slot-name>           # container / inference-bootstrap slot name
PORT=<host-port>           # host port to publish (container always listens on 8000)
GPU=<gpu-index>            # a free GPU index on the node
DEPLOY_DIR=<deploy-dir>    # where the code lives on the node, e.g. /opt/models/cosmos-embed1-pytorch
HF_CACHE=<hf-cache-dir>    # persistent weights cache, e.g. /opt/models/hf-cache
```

---

## 0. Prerequisites (once)
- SSH access to the node.
- A free GPU index (avoid GPUs already used by other slots) and a free host port.
- An NVIDIA NGC / HuggingFace token that can pull `nvidia/Cosmos-Embed1-224p`.

```sh
# confirm free GPUs
ssh $HOST nvidia-smi
# confirm the host port is free
ssh $HOST "docker ps --filter publish=$PORT"
```

---

## 1. Copy the code to the node
From your laptop, in the repo root:

```sh
scp -r deployments/vss-gpu-services/cosmos-embed1-pytorch $HOST:$DEPLOY_DIR
```

(Or `git clone`/`git pull` the branch on the node if it has repo access.)

---

## 2. Build the image (on the node, aarch64)
```sh
ssh $HOST
cd $DEPLOY_DIR
docker build -t cosmos-embed1-pytorch:224p .
```

> The base `nvcr.io/nvidia/pytorch:25.01-py3` provides torch/torchvision built for
> aarch64 CUDA — this is the whole reason it runs where the amd64 NIM can't.

---

## 3. Provide the HF token & cache dir
The first run downloads the weights. Give it a token and a persistent cache so restarts
don't re-download.

```sh
mkdir -p $HF_CACHE
export HF_TOKEN=<your-hf-or-ngc-token>
```

---

## 4. Run the slot (GPU $GPU, host $PORT -> container 8000)
```sh
docker rm -f $SLOT 2>/dev/null || true
docker run -d --name $SLOT \
  --gpus "\"device=$GPU\"" \
  --label inference-bootstrap.model_name=$SLOT \
  --restart unless-stopped \
  -e HF_TOKEN=$HF_TOKEN \
  -e HUGGING_FACE_HUB_TOKEN=$HF_TOKEN \
  -e COSMOS_MODEL_ID=nvidia/Cosmos-Embed1-224p \
  -e COSMOS_NUM_FRAMES=8 \
  -e COSMOS_EMBED_DIM=256 \
  -v $HF_CACHE:/models/hf \
  -p $PORT:8000 \
  cosmos-embed1-pytorch:224p
```

Watch it come up (weights download on first start):
```sh
docker logs -f $SLOT     # wait for "Model ready in ..." and uvicorn "Application startup complete"
```

---

## 5. Verify

**Local (on the node):**
```sh
curl -s localhost:$PORT/health
# {"status":"ok","model":"nvidia/Cosmos-Embed1-224p","dim":256,"frames":8}

# text
curl -s localhost:$PORT/v1/embeddings -H 'Content-Type: application/json' -d '{
  "input": "a red car at night", "request_type": "query", "model": "nvidia/cosmos-embed1"
}' | python3 -c "import sys,json;print('dim',len(json.load(sys.stdin)['data'][0]['embedding']))"

# video
B64=$(base64 -w0 /path/to/clip.mp4)
curl -s localhost:$PORT/v1/embeddings -H 'Content-Type: application/json' -d "{
  \"input\": \"data:video/mp4;base64,${B64}\", \"request_type\": \"query\"
}" | python3 -c "import sys,json;print('dim',len(json.load(sys.stdin)['data'][0]['embedding']))"
```

**Remote (through a gateway, if the node is fronted by one):**
```sh
export TOKEN=<gateway-bearer-token>
curl -s https://<gateway-host>/<tenant>/<slot>/v1/embeddings \
  -H "Authorization: Bearer ${TOKEN}" -H 'Content-Type: application/json' \
  -d '{"input":"a red car at night","request_type":"query"}'
```
If the remote route returns `502`, the container isn't publishing the host port — recheck `-p $PORT:8000`.

---

## 6. Point VSS at this service
Update the retrieval `backend-secret.yaml` and the ingest function secret:

```yaml
embedding_local_nim: true
embeddinghost: <node-ip-or-gateway-host>   # node internal IP, or the gateway host
embeddingport: <port>                      # host port (or 443 if via https gateway)
embeddingmodel: nvidia/cosmos-embed1
embeddinghttpscheme: http                  # https if via gateway
embeddingdimensions: 256
```

Re-apply the retrieval secret + restart backend:
```sh
# from deployments/vss-k8s-application on your machine
sed "s/NAMESPACE/<namespace>/g" backend-secret.yaml | kubectl apply -f -
kubectl rollout restart deployment/video-backend -n <namespace>
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
docker logs -f $SLOT
docker rm -f $SLOT          # stop/remove
docker stats $SLOT          # GPU/mem use

# common issues
# - CUDA OOM        -> pick a less-loaded GPU or use 224p (not 448p)
# - 502 remote      -> container not publishing the expected host port
# - download hangs  -> HF_TOKEN missing/invalid
# - exec format err -> you pulled an amd64 image; this one must be built on the node
```

## Rollback
To revert VSS, point the secret back at a previous x86 NIM host and re-ingest there.
