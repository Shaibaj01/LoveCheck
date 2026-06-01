"""Generate search prompts and key events from segment captions via Cosmos Reason2."""
import json
import logging
import re
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Tuple

import requests
from opentelemetry import trace

from .models import KeyEventSuggestion, Settings, SuggestionsResult

logger = logging.getLogger(__name__)
tracer = trace.get_tracer(__name__)

SYSTEM_PROMPT = """You help operators search a NYC street-safety video index.
You receive scene captions from indexed 5-second clips. Output JSON only.

Goals:
1) search_prompts: exactly {search_count} short natural-language queries a user could paste into semantic search.
   - One sentence each, concrete (objects, colors, brands, street signs, vehicles, pedestrian actions).
   - Grounded ONLY in the provided captions — do not invent scenes.
   - Wording should match how captions describe things (high retrieval similarity).

2) key_events: up to {events_count} notable moments worth investigating.
   - Each needs: query_text (one search sentence), label (short title), original_video, segment_start_sec, segment_end_sec, filename.
   - Pick real timestamps from the input lines.
   - Prefer safety-relevant, unusual, or high-signal activity (conflicts, hazards, costumes, brands, crowds).

Schema:
{{
  "search_prompts": ["...", "..."],
  "key_events": [
    {{
      "query_text": "delivery truck blocking crosswalk",
      "label": "Truck blocking crosswalk",
      "original_video": "s3://bucket/video.mp4",
      "filename": "video.mp4",
      "segment_start_sec": 15.0,
      "segment_end_sec": 20.0
    }}
  ]
}}
"""


def _format_corpus(segments: List[dict], max_lines: int) -> str:
    lines: List[str] = []
    seen_videos = set()
    for seg in segments[:max_lines]:
        ov = str(seg.get("original_video") or seg.get("source") or "").strip()
        if ov in seen_videos and len(seen_videos) > 20:
            continue
        seen_videos.add(ov)
        sn = int(seg.get("segment_number") or 0)
        start = float(seg.get("segment_start_sec") or 0)
        end = float(seg.get("segment_end_sec") or start + 5)
        cap = str(seg.get("dense_caption") or seg.get("reasoning_content") or "")[:400]
        fn = str(seg.get("filename") or ov.rsplit("/", 1)[-1])
        objs = str(seg.get("object_classes") or "")
        lines.append(
            f"- video={ov} | file={fn} | seg={sn} | {start:.0f}-{end:.0f}s | objects={objs} | {cap}"
        )
    return "\n".join(lines)


def _extract_json(text: str) -> Dict[str, Any]:
    cleaned = text.strip()
    if "```" in cleaned:
        match = re.search(r"```(?:json)?\s*(\{.*\})\s*```", cleaned, re.DOTALL)
        if match:
            cleaned = match.group(1)
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start >= 0 and end > start:
        cleaned = cleaned[start : end + 1]
    return json.loads(cleaned)


def _new_batch_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S") + "-" + uuid.uuid4().hex[:8]


def generate_suggestions(
    settings: Settings,
    segments: List[dict],
) -> Tuple[List[str], List[Dict[str, Any]], str]:
    """Call Cosmos chat completions; return prompts, event dicts, batch_id."""
    if not segments:
        return [], [], ""

    batch_id = _new_batch_id()
    corpus = _format_corpus(segments, settings.suggestions_max_segments)
    system = SYSTEM_PROMPT.format(
        search_count=settings.suggestions_search_count,
        events_count=settings.suggestions_events_count,
    )
    user = f"Indexed clip captions ({len(segments)} segments, sample below):\n\n{corpus}"

    payload = {
        "model": settings.cosmos_model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "max_tokens": settings.cosmos_max_tokens,
        "temperature": settings.cosmos_temperature,
    }

    with tracer.start_as_current_span("Cosmos Suggestions LLM") as span:
        span.set_attributes({
            "cosmos_url": settings.cosmos_url,
            "model": settings.cosmos_model,
            "segments_in_corpus": len(segments),
            "corpus_lines": min(len(segments), settings.suggestions_max_segments),
        })
        response = requests.post(settings.cosmos_url, json=payload, timeout=120)
        response.raise_for_status()
        body = response.json()

    content = body["choices"][0]["message"]["content"]
    data = _extract_json(content)
    parsed = SuggestionsResult(
        search_prompts=[str(p).strip() for p in data.get("search_prompts", []) if str(p).strip()],
        key_events=[],
    )
    for ev in data.get("key_events", []):
        if not isinstance(ev, dict) or not ev.get("query_text"):
            continue
        parsed.key_events.append(KeyEventSuggestion.model_validate(ev))

    prompts = parsed.search_prompts[: settings.suggestions_search_count]
    events = [ev.model_dump() for ev in parsed.key_events[: settings.suggestions_events_count]]
    return prompts, events, batch_id
