import logging
from typing import List

from .cosmos_embed_client import CosmosEmbed1Client


class EmbeddingClient:
    """Text embeddings via Cosmos-Embed1 NIM."""

    def __init__(self, settings):
        self._cosmos = CosmosEmbed1Client(settings)
        logging.info(f"[EMBEDDING] Cosmos-Embed1 at {self._cosmos.base_url}")

    def get_embeddings(self, texts: List[str]) -> List[List[float]]:
        return self._cosmos.embed_texts(texts, for_query=False)
