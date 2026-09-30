"""Stream fields for a manual upload.

Chunk numbers in the upload API are 1-based. Explore stores a 0-based
chunk_index and shows "Play chunk {index + 1}/{max index + 1}", so the
displayed count is always 1 + n.
"""
from __future__ import annotations

import re
from typing import Optional

_STREAM_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$")


def stream_s3_metadata(stream_id: str, chunk_number: Optional[int]) -> dict[str, str]:
    """Return S3 metadata that couples this file to a stream, or an empty dict."""
    sid = (stream_id or "").strip()
    if not sid and chunk_number is None:
        return {}
    if not sid:
        raise ValueError("stream_id is required when chunk_number is set")
    if chunk_number is None:
        raise ValueError("chunk_number is required when stream_id is set")
    if chunk_number < 1:
        raise ValueError("chunk_number starts at 1")
    if not _STREAM_ID.match(sid):
        raise ValueError(
            "stream_id must start with a letter or number and contain only "
            "letters, numbers, dots, underscores, or hyphens"
        )
    return {
        "stream_id": sid,
        "chunk_index": str(chunk_number - 1),
        "ingest_kind": "stream_chunk",
    }
