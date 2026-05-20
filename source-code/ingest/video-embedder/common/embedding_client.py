import logging
from typing import List

import requests

from .cosmos_embed_client import CosmosEmbed1Client, is_cosmos_embed1


class EmbeddingClient:
    """Embedding client: OpenAI-style NIM or NVIDIA Cosmos-Embed1."""

    def __init__(self, settings):
        self.settings = settings
        self.model = settings.embeddingmodel
        self.dimensions = settings.embeddingdimensions
        self.provider = getattr(settings, "embedding_provider", "") or ""
        self._cosmos = CosmosEmbed1Client(settings) if is_cosmos_embed1(self.model, self.provider) else None

        if self._cosmos:
            logging.info(f"[EMBEDDING] Using Cosmos-Embed1 at {self._cosmos.base_url}")
            return

        self.nvidia_api_key = getattr(settings, "nvidia_api_key", None) or ""
        self.is_cloud = not getattr(settings, "embedding_local_nim", False)
        self.base_url = f"{settings.embeddinghttpscheme}://{settings.embeddinghost}:{settings.embeddingport}/v1"
        logging.info(f"[EMBEDDING] Using OpenAI-style NIM at {self.base_url}")

    def get_embeddings(self, texts: List[str]) -> List[List[float]]:
        if self._cosmos:
            return self._cosmos.embed_texts(texts)

        headers = {"Content-Type": "application/json"}
        if self.is_cloud and self.nvidia_api_key:
            headers["Authorization"] = f"Bearer {self.nvidia_api_key}"

        payload = {
            "model": self.model,
            "input": texts,
            "input_type": "passage",
        }
        if self.dimensions:
            payload["dimensions"] = self.dimensions

        response = requests.post(
            f"{self.base_url}/embeddings",
            json=payload,
            headers=headers,
            timeout=60,
        )
        if response.status_code != 200:
            logging.error(f"[EMBEDDING] API Error {response.status_code}: {response.text}")
            response.raise_for_status()
        return [item["embedding"] for item in response.json().get("data", [])]
