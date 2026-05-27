import logging
from typing import List

from .cosmos_embed_client import CosmosEmbed1Client, is_cosmos_embed1


class VisualEmbeddingClient:
    """Visual/video embeddings using Cosmos-Embed1 (segment MP4)."""

    def __init__(self, settings):
        self.settings = settings
        text_model = settings.embeddingmodel
        visual_model = settings.visual_embedding_model
        provider = getattr(settings, "embedding_provider", "") or ""

        self._cosmos = (
            CosmosEmbed1Client(settings)
            if is_cosmos_embed1(visual_model, provider) or is_cosmos_embed1(text_model, provider)
            else None
        )

        if not self._cosmos:
            raise RuntimeError(
                "Visual embeddings require Cosmos-Embed1. "
                "Set visual_embedding_model to 'nvidia/cosmos-embed1' "
                "and embedding_provider to 'cosmos_embed1'."
            )
        logging.info("[VISUAL_EMBED] Using Cosmos-Embed1 video embedding (segment MP4)")

    def embed_segment_video(self, video_bytes: bytes) -> List[float]:
        return self._cosmos.embed_video_mp4(video_bytes)
