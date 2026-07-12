"""
Cosmos-Embed1 PyTorch embedding server (arm64 / GB200).

Drop-in replacement for the amd64-only Cosmos-Embed1 NIM. Exposes the same
`POST /v1/embeddings` contract the ingest + retrieval clients already use, so the
only app-side change is pointing `embeddinghost`/`embeddingport` at this service.

Layers:
  server.py    -> HTTP API / endpoints (this file)
  router.py    -> dispatch each input by scheme (text / image / video)
  embedder.py  -> model + preprocessing + embedding (the work the NIM hid)
"""
import logging
import time
from typing import List, Optional, Union

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from embedder import EMBED_DIM, MODEL_ID, NUM_FRAMES, load_model
from router import UnsupportedInput, as_list, route

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("cosmos-embed1.server")


class EmbeddingRequest(BaseModel):
    input: Union[str, List[str]]
    model: Optional[str] = None
    request_type: Optional[str] = "query"   # query | bulk_text | bulk_video (informational)
    encoding_format: Optional[str] = "float"


app = FastAPI(title="Cosmos-Embed1 PyTorch (arm64)")


@app.on_event("startup")
def _startup():
    load_model()


@app.get("/health")
def health():
    return {"status": "ok", "model": MODEL_ID, "dim": EMBED_DIM, "frames": NUM_FRAMES}


@app.post("/v1/embeddings")
def embeddings(req: EmbeddingRequest):
    inputs = as_list(req.input)
    if not inputs:
        raise HTTPException(400, "empty input")
    t0 = time.time()
    try:
        vecs = route(inputs)
    except UnsupportedInput as e:
        raise HTTPException(400, str(e))
    except Exception as e:  # noqa: BLE001
        logger.exception("embedding failed")
        raise HTTPException(500, f"embedding failed: {e}")
    logger.info(
        f"embedded n={len(inputs)} type={req.request_type} in {(time.time() - t0) * 1000:.0f}ms"
    )
    return {
        "object": "list",
        "model": req.model or MODEL_ID,
        "data": [
            {"object": "embedding", "index": i, "embedding": v}
            for i, v in enumerate(vecs)
        ],
        "usage": {"prompt_tokens": 0, "total_tokens": 0},
    }
