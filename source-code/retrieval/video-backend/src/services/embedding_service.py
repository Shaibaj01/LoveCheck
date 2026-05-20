"""
Embedding service for search queries (OpenAI-style NIM or Cosmos-Embed1).
"""
import logging
import requests
import time
from typing import List

from src.config import get_settings
from src.services.cosmos_embed_client import CosmosEmbed1Client, is_cosmos_embed1

logger = logging.getLogger(__name__)
settings = get_settings()


class EmbeddingService:
    """Service for generating embeddings using NVIDIA NIM."""

    def __init__(self):
        self.settings = settings
        self.model = self.settings.embedding_model
        self.provider = getattr(self.settings, "embedding_provider", "") or ""
        self._cosmos = CosmosEmbed1Client() if is_cosmos_embed1(self.model, self.provider) else None

        self.base_url = (
            f"{self.settings.embedding_http_scheme}://"
            f"{self.settings.embedding_host}:{self.settings.embedding_port}/v1"
        )
        self.embedding_url = f"{self.base_url}/embeddings"
        self.dimensions = self.settings.embedding_dimensions

        visual_scheme = self.settings.visual_embedding_http_scheme or self.settings.embedding_http_scheme
        visual_host = self.settings.visual_embedding_host or self.settings.embedding_host
        visual_port = self.settings.visual_embedding_port or self.settings.embedding_port
        self.visual_base_url = f"{visual_scheme}://{visual_host}:{visual_port}/v1"
        self.visual_embedding_url = f"{self.visual_base_url}/embeddings"
        self.visual_model = self.settings.visual_embedding_model
        self.visual_dimensions = self.settings.visual_embedding_dimensions
        self.visual_local_nim = self.settings.visual_embedding_local_nim

        if self._cosmos:
            logger.info(f"Embedding service: Cosmos-Embed1 at {self.base_url}")
        else:
            logger.info(f"Embedding service: OpenAI-style NIM at {self.base_url}")

    def generate_embedding(self, text: str, input_type: str = "query") -> tuple[List[float], float]:
        return self.generate_embeddings([text], input_type=input_type)[0]

    def generate_embeddings(
        self, texts: List[str], input_type: str = "query"
    ) -> List[tuple[List[float], float]]:
        start_time = time.time()
        if self._cosmos:
            vectors = self._cosmos.embed_texts(texts)
            elapsed_ms = (time.time() - start_time) * 1000
            return [(v, elapsed_ms) for v in vectors]

        headers = {"Content-Type": "application/json"}
        if not self.settings.embedding_local_nim and self.settings.nvidia_api_key:
            headers["Authorization"] = f"Bearer {self.settings.nvidia_api_key}"

        payload = {
            "input": texts,
            "model": self.model,
            "encoding_format": "float",
            "input_type": input_type,
        }
        if self.dimensions:
            payload["dimensions"] = self.dimensions

        response = requests.post(self.embedding_url, headers=headers, json=payload, timeout=30)
        if response.status_code != 200:
            raise Exception(f"Embedding API returned {response.status_code}: {response.text}")

        elapsed_ms = (time.time() - start_time) * 1000
        results = []
        for item in response.json().get("data", []):
            embedding = item.get("embedding", [])
            results.append((embedding, elapsed_ms))
        return results

    def generate_visual_embedding(self, text: str, input_type: str = "query") -> tuple[List[float], float]:
        """
        Visual search branch.
        With Cosmos-Embed1, query text is embedded in the same model space as indexed segment videos.
        """
        start_time = time.time()
        if self._cosmos or is_cosmos_embed1(self.visual_model, self.provider):
            client = self._cosmos or CosmosEmbed1Client()
            embedding = client.embed_query_text(text)
            elapsed_ms = (time.time() - start_time) * 1000
            return embedding, elapsed_ms

        headers = {"Content-Type": "application/json"}
        if not self.visual_local_nim and self.settings.nvidia_api_key:
            headers["Authorization"] = f"Bearer {self.settings.nvidia_api_key}"

        payload = {
            "input": text,
            "model": self.visual_model,
            "encoding_format": "float",
            "input_type": input_type,
        }
        if self.visual_dimensions:
            payload["dimensions"] = self.visual_dimensions

        response = requests.post(
            self.visual_embedding_url, headers=headers, json=payload, timeout=60
        )
        if response.status_code != 200:
            raise Exception(f"Visual embedding API returned {response.status_code}: {response.text}")

        elapsed_ms = (time.time() - start_time) * 1000
        data = response.json().get("data", [])
        return data[0]["embedding"], elapsed_ms


_embedding_service: EmbeddingService | None = None


def get_embedding_service() -> EmbeddingService:
    global _embedding_service
    if _embedding_service is None:
        _embedding_service = EmbeddingService()
    return _embedding_service
