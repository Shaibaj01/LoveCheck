"""
NVIDIA Cosmos-Embed1 NIM client (/v1/embeddings).

API differs from OpenAI-style embed models:
  - request_type: query | bulk_text | bulk_video
  - model: nvidia/cosmos-embed1
  - output: 256-dim vectors (no dimensions parameter)
"""
import base64
import logging
from typing import List, Optional

import requests

COSMOS_EMBED1_MODEL = "nvidia/cosmos-embed1"


def is_cosmos_embed1(model: str, provider: str = "") -> bool:
    if (provider or "").lower() in ("cosmos_embed1", "cosmos-embed1"):
        return True
    return "cosmos-embed1" in (model or "").lower() or "cosmos-embed1" in (model or "").lower()


class CosmosEmbed1Client:
    def __init__(self, settings):
        self.model = getattr(settings, "embeddingmodel", COSMOS_EMBED1_MODEL) or COSMOS_EMBED1_MODEL
        if "cosmos-embed" not in self.model.lower():
            self.model = COSMOS_EMBED1_MODEL
        self.nvidia_api_key = getattr(settings, "nvidia_api_key", None) or ""
        self.is_cloud = not getattr(settings, "embedding_local_nim", False)
        scheme = getattr(settings, "embeddinghttpscheme", "http") or "http"
        host = getattr(settings, "embeddinghost", "localhost")
        port = getattr(settings, "embeddingport", 8002)
        self.base_url = f"{scheme}://{host}:{port}/v1"
        self.expected_dim = int(getattr(settings, "embeddingdimensions", 256) or 256)

    def _headers(self) -> dict:
        headers = {"Content-Type": "application/json"}
        if self.is_cloud and self.nvidia_api_key:
            headers["Authorization"] = f"Bearer {self.nvidia_api_key}"
        return headers

    def _post(self, payload: dict, timeout: int = 120) -> List[List[float]]:
        url = f"{self.base_url}/embeddings"
        response = requests.post(url, json=payload, headers=self._headers(), timeout=timeout)
        if response.status_code != 200:
            logging.error(f"[COSMOS_EMBED] {response.status_code}: {response.text[:500]}")
            response.raise_for_status()
        items = response.json().get("data", [])
        vectors = [item.get("embedding", []) for item in items if item.get("embedding")]
        if not vectors:
            raise RuntimeError("Cosmos-Embed1 returned no embeddings")
        return vectors

    def embed_texts(self, texts: List[str], *, for_query: bool = False) -> List[List[float]]:
        if not texts:
            return []
        if len(texts) == 1:
            payload = {
                "input": texts[0],
                "model": self.model,
                "request_type": "query",
                "encoding_format": "float",
            }
        else:
            payload = {
                "input": texts,
                "model": self.model,
                "request_type": "bulk_text",
                "encoding_format": "float",
            }
        logging.info(
            f"[COSMOS_EMBED] Text embed | n={len(texts)} | query_mode={for_query}"
        )
        return self._post(payload)

    def embed_video_mp4(self, video_bytes: bytes) -> List[float]:
        """Embed a short segment MP4 (query mode, base64 video)."""
        if not video_bytes:
            raise ValueError("Empty video bytes")
        b64 = base64.b64encode(video_bytes).decode("ascii")
        payload = {
            "input": f"data:video/mp4;base64,{b64}",
            "model": self.model,
            "request_type": "query",
            "encoding_format": "float",
        }
        logging.info(f"[COSMOS_EMBED] Video embed | {len(video_bytes)} bytes")
        vectors = self._post(payload, timeout=180)
        return vectors[0]

    def embed_query_text(self, text: str) -> List[float]:
        return self.embed_texts([text], for_query=True)[0]
