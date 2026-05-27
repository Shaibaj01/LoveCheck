"""Cosmos-Embed1 NIM client for backend search embeddings."""
import base64
import logging
from typing import List

import requests

from src.config import get_settings

logger = logging.getLogger(__name__)

COSMOS_EMBED1_MODEL = "nvidia/cosmos-embed1"


class CosmosEmbed1Client:
    def __init__(self):
        settings = get_settings()
        self.model = settings.embedding_model
        if "cosmos-embed" not in (self.model or "").lower():
            self.model = COSMOS_EMBED1_MODEL
        self.is_cloud = not settings.embedding_local_nim
        self.base_url = (
            f"{settings.embedding_http_scheme}://"
            f"{settings.embedding_host}:{settings.embedding_port}/v1"
        )
        self.nvidia_api_key = settings.nvidia_api_key
        self.expected_dim = settings.embedding_dimensions

    def _headers(self) -> dict:
        headers = {"Content-Type": "application/json"}
        if self.is_cloud and self.nvidia_api_key:
            headers["Authorization"] = f"Bearer {self.nvidia_api_key}"
        return headers

    def embed_texts(self, texts: List[str]) -> List[List[float]]:
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
        url = f"{self.base_url}/embeddings"
        response = requests.post(url, json=payload, headers=self._headers(), timeout=60)
        if response.status_code != 200:
            raise RuntimeError(f"Cosmos-Embed1 error {response.status_code}: {response.text}")
        return [item["embedding"] for item in response.json().get("data", [])]

    def embed_query_text(self, text: str) -> List[float]:
        return self.embed_texts([text])[0]
