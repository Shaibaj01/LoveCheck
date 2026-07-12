"""
Request routing: map each input to the right embedding path by its scheme.

This is the "router" the NIM API implied — it inspects the input format and
dispatches to the functionality in `embedder.py`. It does NOT run the model or
decode media itself; it only decides which path each input takes.

Schemes:
  - plain text                        -> embed_texts
  - data:image/<fmt>;base64,...       -> image_to_frames -> embed_videos
  - data:video/<fmt>;base64,...       -> decode_mp4      -> embed_videos
"""
import base64
import re
from typing import List, Union

from embedder import decode_mp4, embed_texts, embed_videos, image_to_frames

DATA_URI_RE = re.compile(r"^data:(?P<kind>[\w/+.-]+);base64,(?P<b64>.+)$", re.DOTALL)


class UnsupportedInput(ValueError):
    pass


def as_list(x: Union[str, List[str]]) -> List[str]:
    return x if isinstance(x, list) else [x]


def route(inputs: List[str]) -> List[List[float]]:
    """Route each input by scheme, batch text and media separately, then
    reassemble results in the original order."""
    texts: List[str] = []
    clips: List["object"] = []
    kinds: List[str] = []  # "text" | "media", preserves order

    for item in inputs:
        m = DATA_URI_RE.match(item)
        if not m:
            texts.append(item)
            kinds.append("text")
            continue
        kind = m.group("kind").lower()
        raw = base64.b64decode(m.group("b64"))
        if kind.startswith("image/"):
            clips.append(image_to_frames(raw))
        elif kind.startswith("video/"):
            clips.append(decode_mp4(raw))
        else:
            raise UnsupportedInput(f"unsupported input scheme: {kind}")
        kinds.append("media")

    text_vecs = embed_texts(texts) if texts else []
    media_vecs = embed_videos(clips) if clips else []

    result: List[List[float]] = []
    ti = mi = 0
    for k in kinds:
        if k == "text":
            result.append(text_vecs[ti]); ti += 1
        else:
            result.append(media_vecs[mi]); mi += 1
    return result
