# `deploy.sh` — VSS GPU services on RTX

Deploy **Cosmos-Reason2**, **Cosmos-Embed1**, and **YOLO11** with Docker on a bare-metal
GPU host. Run `deploy.sh` from this directory (`scripts/vss-blueprint-models/`) on the machine that has the GPUs.

---

## What it deploys


| Service | Container           | Default port | GPU              | Image                                        |
| ------- | ------------------- | ------------ | ---------------- | -------------------------------------------- |
| Reason2 | `cosmos-reason2-8b` | **8001**     | `REASONER_GPU`   | `nvcr.io/nim/nvidia/cosmos-reason2-8b:1.7.0` |
| Embed1  | `cosmos-embed1`     | **8002**     | `EMBED_YOLO_GPU` | `nvcr.io/nim/nvidia/cosmos-embed1:1.1.0`     |
| YOLO    | `yolo-infer`        | **8003**     | `EMBED_YOLO_GPU` | `yolo-infer:latest` (built locally)          |


**GPU layout:** Embed1 and YOLO share the first GPU. Reason2 uses the second GPU when given; with **one** GPU, all selected services share that device.

**VSS secrets:** set `cosmos_host` / `cosmos_port` (8001), `embeddinghost` / `embeddingport` (8002), `yolo_infer_host` / `yolo_infer_port` (8003) to this host. If a template still shows YOLO `8022`, override `--yolo-port` or change the secret to **8003**.

---

## Prerequisites

- NVIDIA driver + `nvidia-smi`
- Docker + [NVIDIA Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/install-guide.html)
- NGC API key ([generate here](https://org.ngc.nvidia.com/setup/api-key))
- NGC licenses accepted for [Cosmos-Reason2-8b](https://catalog.ngc.nvidia.com/orgs/nim/nvidia/containers/cosmos-reason2-8b) and [Cosmos-Embed1](https://catalog.ngc.nvidia.com/orgs/nim/nvidia/containers/cosmos-embed1)
- YOLO sources in `yolo-infer/` next to `deploy.sh` (or set `YOLO_INFER_DIR`)

```bash
chmod +x deploy.sh
```

---

## Quick start

From the blueprint repo:

```bash
cd scripts/vss-blueprint-models
export NGC_API_KEY='<your-ngc-api-key>'
./deploy.sh EMBED_YOLO_GPU REASONER_GPU
```

- One arg — all selected services on that GPU
- Two args — embed+yolo on the first, Reason2 on the second

Examples:

```bash
./deploy.sh 2                          # all three on GPU 2
./deploy.sh --embedder --yolo 2        # embedder + YOLO on GPU 2
./deploy.sh 2 3 --reasoner-port 8001 --embed-port 8002 --yolo-port 8003
```

Defaults are **8001 / 8002 / 8003** (VSS convention). Override only when ports clash.

The script logs into `nvcr.io`, starts containers, then **polls health** (shows `loading` while
NIM downloads/starts; `ok` when ready). First NIM start can take several minutes.

| Variable | Default | Purpose |
|----------|---------|---------|
| `HEALTH_WAIT_SEC` | `600` | Max seconds to wait per service (Reason2 uses this; embed 180s, yolo 120s) |

---

## Arguments


| Positional     | Meaning                                                                 |
| -------------- | ----------------------------------------------------------------------- |
| `GPU`          | First GPU (embed+yolo; also Reason2 if `REASONER_GPU` omitted)          |
| `REASONER_GPU` | Optional. GPU for Reason2; if omitted, Reason2 uses the same GPU as above |

---

## Options


| Flag                | Description                                             |
| ------------------- | ------------------------------------------------------- |
| `--all`             | Deploy all three (default if no service flag is given)  |
| `--reasoner`        | Deploy Reason2 only                                     |
| `--embedder`        | Deploy Embed1 only                                      |
| `--yolo`            | Deploy YOLO only                                        |
| `--reasoner-port P` | Host port for Reason2 (default `8001`)                  |
| `--embed-port P`    | Host port for Embed1 (default `8002`)                   |
| `--yolo-port P`     | Host port for YOLO (default `8003`)                     |
| `--ngc-api-key K`   | NGC API key (alternative to `NGC_API_KEY` env)          |
| `--build-yolo`      | Force `docker build` even if `yolo-infer:latest` exists |
| `-h`, `--help`      | Show usage                                              |


Combine service flags:

```bash
./deploy.sh --embedder --yolo 2   # embedder + yolo on GPU 2
./deploy.sh --reasoner 3          # reasoner only on GPU 3
./deploy.sh --yolo --build-yolo 2
./deploy.sh --embedder --yolo 2 3 # same (second GPU unused if reasoner not deployed)
```

---

## Environment variables


| Variable         | Default                                             | Purpose                            |
| ---------------- | --------------------------------------------------- | ---------------------------------- |
| `NGC_API_KEY`    | (prompt if TTY)                                     | Pull NIM weights from NGC          |
| `REASONER_PORT`  | `8001`                                              | Reason2 host port                  |
| `EMBED_PORT`     | `8002`                                              | Embed1 host port                   |
| `YOLO_PORT`      | `8003`                                              | YOLO host port                     |
| `YOLO_INFER_DIR` | `yolo-infer` (sibling of `deploy.sh` in this dir)  | YOLO source for build + bind mount |
| `YOLO_IMAGE`     | `yolo-infer:latest`                                 | Docker image tag for YOLO          |


If `YOLO_IMAGE` is missing locally, the script builds it once automatically (no flag needed).
Use `--build-yolo` to rebuild. On hosts with an old `yolo:latest` image only, either build or set `YOLO_IMAGE=yolo:latest`.

---

## Verify

After deploy (or wait for NIM download to finish):

```bash
curl -s "http://127.0.0.1:${REASONER_PORT:-8001}/v1/health/ready"
curl -s "http://127.0.0.1:${EMBED_PORT:-8002}/v1/health/ready"
curl -s "http://127.0.0.1:${YOLO_PORT:-8003}/healthz"
```

```bash
docker ps --format 'table {{.Names}}\t{{.Ports}}\t{{.Status}}' \
  | grep -E 'cosmos-reason2|cosmos-embed1|yolo-infer|NAMES'
nvidia-smi
```

---

## Tear down

```bash
docker rm -f cosmos-reason2-8b cosmos-embed1 yolo-infer
```

NIM caches stay in `~/.cache/nim/` for faster redeploys.

---

## Troubleshooting


| Issue                          | Fix                                                                                                                       |
| ------------------------------ | ------------------------------------------------------------------------------------------------------------------------- |
| `NGC_API_KEY is empty`         | `export NGC_API_KEY=...` or `--ngc-api-key`                                                                               |
| Reason2 health not 200 yet     | Wait for model download; `docker logs -f cosmos-reason2-8b`                                                               |
| Reason2 OOM                    | Pick a freer `REASONER_GPU`; or add `-e 'NIM_PASSTHROUGH_ARGS=--gpu-memory-utilization 0.85'` to the Reason2 `docker run` |
| YOLO `cuda_available: false`   | Ensure `--runtime=nvidia` (script does this); check `nvidia-smi`                                                          |
| `yolo-infer/main.py not found` | Run from `scripts/vss-blueprint-models`, or set `YOLO_INFER_DIR` to a directory that contains `main.py`                   |
| Port in use                    | `docker ps` / stop old `yolo-object` or other container on 8001/8002/8003                                                 |
