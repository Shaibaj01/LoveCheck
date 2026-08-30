"""Embedding service for search queries (Cosmos-Embed1)."""
import logging
import time
from typing import List

from src.config import get_settings
from src.services.cosmos_embed_client import CosmosEmbed1Client

logger = logging.getLogger(__name__)
settings = get_settings()


class EmbeddingService:
    """Service for generating embeddings using Cosmos-Embed1."""

    def __init__(self):
        self.settings = settings
        self._cosmos = CosmosEmbed1Client()
        logger.info(f"Embedding service: Cosmos-Embed1 at {self._cosmos.base_url}")

    def generate_embedding(self, text: str, input_type: str = "query") -> tuple[List[float], float]:
        return self.generate_embeddings([text], input_type=input_type)[0]

    def generate_embeddings(
        self, texts: List[str], input_type: str = "query"
    ) -> List[tuple[List[float], float]]:
        start_time = time.time()
        vectors = self._cosmos.embed_texts(texts)
        elapsed_ms = (time.time() - start_time) * 1000
        return [(v, elapsed_ms) for v in vectors]

    def generate_visual_embedding(self, text: str, input_type: str = "query") -> tuple[List[float], float]:
        """Hybrid visual branch: embed query text in the same Cosmos-Embed1 space as indexed videos."""
        start_time = time.time()
        embedding = self._cosmos.embed_query_text(text)
        elapsed_ms = (time.time() - start_time) * 1000
        return embedding, elapsed_ms


_embedding_service: EmbeddingService | None = None


def get_embedding_service() -> EmbeddingService:
    global _embedding_service
    if _embedding_service is None:
        _embedding_service = EmbeddingService()
    return _embedding_service
