# Deploy K8s Application (Backend/Frontend)

Deploy the VSS Blueprint web application to Kubernetes.

## Prerequisites

- **Kubernetes access:**
  - `kubectl` installed and configured for your cluster
  - Ability to create namespaces and deploy resources

- **VAST cluster access:**
  - Cluster name (e.g., `v1234`) - used as part of the URL
  - VMS hostname and tenant name for user authentication (see [User Authentication](../../source-code/retrieval/video-backend/README.md))

- **Storage resources:**
  - S3 buckets: `vss-chunks` and `vss-chunks-segments` (segmenter writes `{upload_bucket}-segments` by default)
  - VastDB bucket: `vss-db`, schema `vss-schema`, tables `vss-collection` and `vss-prompts-events`

- **AI/ML services:**
  - Cosmos-Embed1 NIM (hybrid search embeddings)
  - Cosmos-Reason2 NIM (search/explore synthesis; same host as ingest reasoner)
  - Optional NVIDIA Cloud API key when `embedding_local_nim: false`

- **Network access:**
  - Ability to modify `/etc/hosts` on your local machine

---

## Step 1: Configure Backend Secret

Copy the example and fill in credentials locally (**do not commit** `backend-secret.yaml`):

```bash
cp backend-secret.yaml.example backend-secret.yaml
vim backend-secret.yaml
```

| Section | Key Settings |
|---------|--------------|
| **VastDB** | `vdb_endpoint`, `vdb_bucket` (`vss-db`), `vdb_schema` (`vss-schema`), `vdb_collection` (`vss-collection`), `vdb_prompts_collection` (`vss-prompts-events`), credentials |
| **S3** | `s3_endpoint` (must match tenant), `s3_upload_bucket` (`vss-chunks`), `s3_segments_bucket` (`vss-chunks-segments`), credentials |
| **Cosmos-Embed1** | `embedding_host`, `embedding_port`, `embedding_model`, `embedding_local_nim`, `nvidia_api_key` |
| **Cosmos-Reason2** | `cosmos_host`, `cosmos_port`, `cosmoshttpscheme`, `cosmos_model`, `synthesis_*` |
| **UI** | `display_timezone` (IANA, e.g. `Asia/Jerusalem`) |
| **Auth** | `vast_host`, `tenant_name`, `jwt_secret` (see [setup](../../source-code/retrieval/video-backend/README.md#user-authentication)) |

---

## Step 2: Docker Images

Build images with the helper script (recommended) or manually. Replace registry paths in each `*-deployment.yaml`.

```bash
# Recommended — sets ECR/TAG; builds backend, frontend, streaming, batch-sync
ECR=your.registry/vss TAG=v2 source-code/scripts/build-retrieval-images.sh
```

Manual builds from `source-code/` as context (see [shared README](../source-code/shared/README.md#docker-builds)):

```bash
cd source-code

docker buildx build -f retrieval/video-backend/Dockerfile -t your.registry/vss-video-backend:v2 --push .

docker buildx build -f retrieval/video-frontend/Dockerfile -t your.registry/vss-video-frontend:v2 --push retrieval/video-frontend

docker buildx build -f video-streaming/Dockerfile -t your.registry/vss-video-streaming:v2 --push .

docker buildx build -f video-batch-sync/Dockerfile -t your.registry/vss-video-batch-sync:v2 --push .
```

If your cluster requires a specific architecture (for example `linux/amd64`), add `--platform linux/amd64` to each `docker build`. Ensure your registry is reachable from the cluster (image pull secrets if the registry is private).

---

## Step 3: Deploy

```bash
./QUICK_DEPLOY.sh <namespace> <cluster_name>

# Example:
./QUICK_DEPLOY.sh vastvideo v1234
```

**What gets deployed:**
- Backend Service (FastAPI) - REST API
- Frontend Service (Angular) - Web UI
- Video Streaming Service - YouTube capture
- Video Batch Sync Service - S3 copy
- Ingress Resources - External access

---

## Step 4: Wait for Pods

```bash
kubectl get pods -n <namespace> -w
```

---

## Step 5: Configure DNS

Get ingress IP:
```bash
kubectl get ingress -n <namespace>
```

Add to `/etc/hosts` (on your local machine):
```
<INGRESS_IP> video-lab.<cluster_name>.vastdata.com
```

---

## Step 6: Access UI

```
http://video-lab.<cluster_name>.vastdata.com
```

---

## Troubleshooting

### Cannot access web UI
- Check pods: `kubectl get pods -n <namespace>`
- Check ingress: `kubectl get ingress -n <namespace>`
- Verify `/etc/hosts` entry

### Authentication fails
- Verify `s3_endpoint` matches tenant
- See [Auth Troubleshooting](../../source-code/retrieval/video-backend/README.md#troubleshooting)

### View Logs

```bash
# Backend
kubectl logs -f -n <namespace> -l app=video-backend

# Frontend  
kubectl logs -f -n <namespace> -l app=video-frontend

# Streaming
kubectl logs -f -n <namespace> -l app=video-stream-capture

# Batch Sync
kubectl logs -f -n <namespace> -l app=video-batch-sync
```
