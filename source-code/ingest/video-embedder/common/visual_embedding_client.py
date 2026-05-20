import base64
import logging
from typing import List, Optional

import requests

from .cosmos_embed_client import CosmosEmbed1Client, is_cosmos_embed1


class VisualEmbeddingClient:
    """Visual/video embeddings: Cosmos-Embed1 (segment MP4) or OpenAI-style frame images."""

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

        if self._cosmos:
            logging.info("[VISUAL_EMBED] Using Cosmos-Embed1 video embedding (segment MP4)")
            return

        self.model = visual_model
        self.dimensions = settings.visual_embedding_dimensions
        self.nvidia_api_key = getattr(settings, "nvidia_api_key", None) or ""
        self.is_cloud = not getattr(settings, "visual_embedding_local_nim", False)
        self.base_url = (
            f"{settings.visual_embedding_httpscheme}://"
            f"{settings.visual_embedding_host}:{settings.visual_embedding_port}/v1"
        )
        self.num_frames = int(getattr(settings, "visual_embedding_num_frames", 3) or 3)

    def _headers(self) -> dict:
        headers = {"Content-Type": "application/json"}
        if self.is_cloud and self.nvidia_api_key:
            headers["Authorization"] = f"Bearer {self.nvidia_api_key}"
        return headers

    def embed_segment_video(self, video_bytes: bytes) -> List[float]:
        """Preferred path for Cosmos-Embed1: embed full segment MP4."""
        if self._cosmos:
            return self._cosmos.embed_video_mp4(video_bytes)
        raise RuntimeError("embed_segment_video requires Cosmos-Embed1")

    def embed_frame_pngs(self, frame_png_bytes: List[bytes], input_type: str = "passage") -> List[float]:
        if self._cosmos:
            raise RuntimeError(
                "Cosmos-Embed1 uses full segment video; call embed_segment_video instead of frame PNGs"
            )

        if not frame_png_bytes:
            raise ValueError("No frames to embed")

        if len(frame_png_bytes) == 1:
            inputs = [{
                "type": "image_url",
                "image_url": {
                    "url": f"data:image/png;base64,{base64.b64encode(frame_png_bytes[0]).decode()}"
                },
            }]
        else:
            inputs = []
            for frame in frame_png_bytes:
                inputs.append({
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/png;base64,{base64.b64encode(frame).decode()}"
                    },
                })

        payload = {
            "model": self.model,
            "input": inputs,
            "input_type": input_type,
            "encoding_format": "float",
        }
        if self.dimensions:
            payload["dimensions"] = self.dimensions

        response = requests.post(
            f"{self.base_url}/embeddings",
            json=payload,
            headers=self._headers(),
            timeout=120,
        )
        if response.status_code != 200:
            logging.error(f"[VISUAL_EMBED] API error {response.status_code}: {response.text[:500]}")
            response.raise_for_status()

        vectors = [
            item.get("embedding", [])
            for item in response.json().get("data", [])
            if item.get("embedding")
        ]
        if not vectors:
            raise RuntimeError("Visual embedding API returned empty vectors")
        if len(vectors) == 1:
            return vectors[0]

        dim = len(vectors[0])
        pooled = [0.0] * dim
        for vec in vectors:
            if len(vec) != dim:
                raise RuntimeError("Inconsistent visual embedding dimensions in batch response")
            for i, val in enumerate(vec):
                pooled[i] += float(val)
        count = float(len(vectors))
        return [v / count for v in pooled]
