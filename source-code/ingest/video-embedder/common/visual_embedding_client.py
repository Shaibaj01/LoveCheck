import logging
from typing import List

from .cosmos_embed_client import CosmosEmbed1Client


class VisualEmbeddingClient:
    """Visual/video embeddings using Cosmos-Embed1 (segment MP4)."""

    def __init__(self, settings):
        self._cosmos = CosmosEmbed1Client(settings)
        logging.info("[VISUAL_EMBED] Cosmos-Embed1 video embedding (segment MP4)")

    def embed_segment_video(self, video_bytes: bytes) -> List[float]:
        return self._cosmos.embed_video_mp4(video_bytes)
